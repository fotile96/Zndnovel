#!/usr/bin/env -S uv run python
"""层系统：基座 + 层 + 剖面的加载、校验、施加与取证。

设计见 docs/superpowers/specs/2026-09-02-disc-layers-pipeline-design.md。

核心约束：叠加层在**译文注入之后**施加（账本按 (file, line) 锚定，注入必须先跑
且行号不变），故锚点只准是代码文本，不准是可译文本，不准是行号。
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


class OverlayError(SystemExit):
    """叠加层施加失败。继承 SystemExit：正确性问题一律硬失败，不给静默机会。"""


def find_all(text: str, needle: str) -> list[int]:
    """自左向右非重叠查找，返回全部起点。"""
    if not needle:
        raise OverlayError("锚点为空串——叠加层写错了")
    hits, i = [], 0
    while (j := text.find(needle, i)) >= 0:
        hits.append(j)
        i = j + len(needle)
    return hits


def select_indices(hits: list[int], count: int, occurrence) -> list[int]:
    """按 count 断言总命中数，按 occurrence 选出要作用的那几处。"""
    # count=0 必须挡住：否则「锚点根本不存在」与「期望零命中」在数值上一样，
    # 施加就成了静默 no-op——而 count 存在的全部理由正是抓这种漂移。
    if count < 1:
        raise OverlayError(f"count 必须 ≥1，收到 {count}——零命中的层等于没写")
    if len(hits) != count:
        raise OverlayError(
            f"锚点期望命中 {count} 处，实际命中 {len(hits)} 处——"
            f"基座变了或叠加层写错了。用 `uv run python tools/layers.py diff <层名>` 核对")
    if occurrence == "all":
        return hits
    if not isinstance(occurrence, int) or occurrence == 0:
        raise OverlayError(f"occurrence 必须是 \"all\" 或非零整数，收到 {occurrence!r}")
    idx = occurrence - 1 if occurrence > 0 else count + occurrence
    if not 0 <= idx < count:
        raise OverlayError(f"occurrence={occurrence} 越界（命中 {count} 处）")
    return [hits[idx]]


def _need(op: dict, *keys: str) -> tuple:
    missing = [k for k in keys if k not in op]
    if missing:
        raise OverlayError(f"操作 {op.get('op')!r} 缺字段 {missing}")
    return tuple(op[k] for k in keys)


def _apply_point_op(text: str, op: dict, anchor: str, render) -> str:
    """replace / insert_before / insert_after 共用：定位 → 选点 → 自后向前改写。"""
    picks = select_indices(find_all(text, anchor), op.get("count", 1),
                           op.get("occurrence", "all"))
    for start in reversed(picks):        # 自后向前，前面的下标不受影响
        end = start + len(anchor)
        text = text[:start] + render(text[start:end]) + text[end:]
    return text


def _apply_span_op(text: str, op: dict, replacement: str) -> str:
    start_s, end_s = _need(op, "start", "end")
    if "count" in op or "occurrence" in op:
        raise OverlayError("span 类操作不接受 count / occurrence——两个锚各须恰好命中一次")
    starts, ends = find_all(text, start_s), find_all(text, end_s)
    if len(starts) != 1:
        raise OverlayError(f"start 锚点须恰好命中 1 次，实际 {len(starts)} 次")
    if len(ends) != 1:
        raise OverlayError(f"end 锚点须恰好命中 1 次，实际 {len(ends)} 次")
    if ends[0] < starts[0]:
        raise OverlayError("end 锚点在 start 之前——区间无效")
    return text[:starts[0]] + replacement + text[ends[0] + len(end_s):]


def apply_op(text: str, op: dict) -> str:
    """施加单个操作。五种：replace / insert_before / insert_after / delete_span / replace_span。"""
    kind = op.get("op")
    if kind == "replace":
        find, with_ = _need(op, "find", "with")
        return _apply_point_op(text, op, find, lambda _: with_)
    if kind == "insert_before":
        anchor, ins = _need(op, "anchor", "text")
        return _apply_point_op(text, op, anchor, lambda hit: ins + hit)
    if kind == "insert_after":
        anchor, ins = _need(op, "anchor", "text")
        return _apply_point_op(text, op, anchor, lambda hit: hit + ins)
    if kind == "delete_span":
        return _apply_span_op(text, op, "")
    if kind == "replace_span":
        (with_,) = _need(op, "with")
        return _apply_span_op(text, op, with_)
    raise OverlayError(f"未知操作 {kind!r}（可选 replace / insert_before / insert_after / "
                       f"delete_span / replace_span）")


def apply_overlay(text: str, overlay: dict) -> str:
    """按声明顺序依次施加全部操作；每个操作看到的都是前序操作之后的文本。"""
    for i, op in enumerate(overlay.get("ops", []), 1):
        try:
            text = apply_op(text, op)
        except OverlayError as exc:
            name = overlay.get("_name", "?")
            raise OverlayError(f"叠加层 {name} 第 {i} 个操作失败：{exc}") from None
    return text


import tomllib

LAYERS = REPO / "layers"
PROFILES = ("release", "test")
CARD_MSG_RESERVED = range(18001, 18196)   # oCard.show 动态 id = 18000 + 卡号（卡 1..195）

_MANIFEST_KEYS = {"base", "lane", "compiler", "overlays", "scripts", "gim", "fonts"}
_OVERLAY_KEYS = {"target", "profile", "why", "switch", "ops"}


def _read_toml(path: Path) -> dict:
    if not path.exists():
        raise OverlayError(f"缺 {path}")
    with open(path, "rb") as f:
        try:
            return tomllib.load(f)
        except tomllib.TOMLDecodeError as exc:
            raise OverlayError(f"{path} 不是合法 TOML：{exc}") from None


def load_overlay(path: Path) -> dict:
    """读一个叠加层文件并校验。`_name` = 文件名去 .toml。"""
    d = _read_toml(path)
    unknown = set(d) - _OVERLAY_KEYS
    if unknown:
        raise OverlayError(f"{path.name} 有未知键 {sorted(unknown)}")
    for key in ("target", "profile", "why"):
        if not d.get(key):
            raise OverlayError(f"{path.name} 缺 {key}（why 必须写清依据，不许留空）")
    if d["profile"] not in PROFILES:
        raise OverlayError(f"{path.name} 的 profile={d['profile']!r} 非法（只能 {PROFILES}）")
    if not d.get("ops"):
        raise OverlayError(f"{path.name} 没有任何 [[ops]]")
    d["_name"] = path.stem
    return d


def load_manifest(root: Path = LAYERS) -> dict:
    """读清单并校验：未知键报错；order 必须与 overlays/ 下的文件一一对应。"""
    man = _read_toml(root / "manifest.toml")
    unknown = set(man) - _MANIFEST_KEYS
    if unknown:
        raise OverlayError(f"manifest.toml 有未知键 {sorted(unknown)}")
    for key in ("base", "lane", "compiler", "overlays"):
        if key not in man:
            raise OverlayError(f"manifest.toml 缺 [{key}]")
    order = man["overlays"].get("order", [])
    on_disk = sorted(p.stem for p in (root / "overlays").glob("*.toml"))
    if sorted(order) != on_disk:
        raise OverlayError(
            f"manifest.toml 的 overlays.order 与 layers/overlays/ 下的文件不一致：\n"
            f"  order  = {sorted(order)}\n  on disk = {on_disk}\n"
            f"新加的层必须在 order 里排位置——施加顺序是语义的一部分")
    man.setdefault("scripts", [])
    man.setdefault("gim", {"replace": [], "new": []})
    man.setdefault("fonts", [])
    return man


def overlays_for(manifest: dict, root: Path, profile: str, switches: dict) -> list[dict]:
    """按 order 取该剖面要施加的层。release 层在两个剖面都施加；test 层只在 test。

    switches: {开关名: bool}。带 switch 的层缺省施加，显式给 False 才关掉。
    """
    if profile not in PROFILES:
        raise OverlayError(f"未知剖面 {profile!r}")
    out = []
    for name in manifest["overlays"]["order"]:
        ov = load_overlay(root / "overlays" / f"{name}.toml")
        if ov["profile"] == "test" and profile != "test":
            continue
        if "switch" in ov and switches.get(ov["switch"], True) is False:
            continue
        out.append(ov)
    return out


import re as _re

#: 只认真正的调用：`vms(N,` / `msg(N,`。左侧的 (?<![A-Za-z0-9_]) 挡住 xmsg(/debagMsg( 之类。
_ID_CALL_RE = _re.compile(r"(?<![A-Za-z0-9_])(?:vms|msg)\((\d+),")


def collect_ids(text: str) -> set[int]:
    """扫一段 lua（或叠加层的 with/text 字段）里出现的全部消息 id。"""
    return {int(m.group(1)) for m in _ID_CALL_RE.finditer(text)}


def _ranges_of(entry: dict, key: str) -> list[range]:
    out = []
    for pair in entry.get(key, []):
        lo, hi = pair
        if lo > hi:
            raise OverlayError(f"区段 [{lo}, {hi}] 顺序颠倒（owner={entry.get('owner')}）")
        out.append(range(lo, hi + 1))
    return out


def check_ids(manifest: dict, root: Path, ledger_ids: set[int]) -> None:
    """id 登记检查：落在本层区段内、owner 区段两两不交、不与保留集相交、全局唯一。

    保留集 = 账本 id ∪ [18001, 18195]（卡消息由引擎按 18000 + 卡号动态生成）。
    `[[ranges]]` 可选 `profile`（缺省 "release"）。test 层（探针沿用 9000 段，
    测试盘永不出货）免于与保留集比对，但两两不交、以及下面脚本扫描里的「全局
    唯一」两道对 test 层同样生效——「免检」只免保留集这一项，不是整层放行。
    """
    reg = _read_toml(root / "vms_ids.toml")
    owned: dict[str, tuple[str, list[range]]] = {}
    for entry in reg.get("ranges", []):
        owner = entry.get("owner")
        if not owner:
            raise OverlayError("vms_ids.toml 有 [[ranges]] 缺 owner")
        profile = entry.get("profile", "release")
        if profile not in PROFILES:
            raise OverlayError(f"vms_ids.toml 里 {owner} 的 profile={profile!r} 非法"
                               f"（只能 {PROFILES}）")
        owned[owner] = (profile, _ranges_of(entry, "vms") + _ranges_of(entry, "card_msg"))

    seen: dict[int, str] = {}
    for owner, (profile, rs) in owned.items():
        for r in rs:
            for other, (_, ors) in owned.items():
                if other <= owner:
                    continue
                for o in ors:
                    if max(r.start, o.start) < min(r.stop, o.stop):
                        raise OverlayError(
                            f"id 区段重叠：{owner} 与 {other} 在 "
                            f"[{max(r.start, o.start)}, {min(r.stop, o.stop) - 1}] 相交")
            if profile == "test":
                continue  # 探针沿用 9000 段，与账本/卡消息保留集大概率相交，故只查两两不交
            hit = sorted(set(r) & (ledger_ids | set(CARD_MSG_RESERVED)))
            if hit:
                raise OverlayError(
                    f"{owner} 声明的区段撞上保留 id {hit[:5]}"
                    f"（账本 1..17220 与卡消息 18001..18195 已占）")

    for spec in manifest["scripts"]:
        # 不再按 spec 的 profile 整体跳过——test 层脚本仍须落在自己声明的区段内、
        # 且不与其他 owner 撞号；只是否与账本比对这一件事，由 owner 在 vms_ids.toml
        # 里登记的 profile 决定（见 _check_ids_of）。
        # spec["file"] 形如 "scripts/snr_finale.lua"，相对 layers/ 根。
        # 用传进来的 root 而不是模块级 LAYERS——夹具测试要能指向 tmp_path。
        text = (root / spec["file"]).read_text(encoding="utf-8")
        _check_ids_of(spec["file"], text, owned, seen, ledger_ids)


def _check_ids_of(owner: str, text: str, owned, seen, ledger_ids) -> None:
    entry = owned.get(owner)
    if entry is None:
        raise OverlayError(f"{owner} 没有在 layers/vms_ids.toml 登记 id 区段")
    profile, ranges = entry
    for i in sorted(collect_ids(text)):
        if not any(i in r for r in ranges):
            raise OverlayError(
                f"{owner} 用了 id {i}，不在其声明的区段内——"
                f"在 layers/vms_ids.toml 里扩段，或改用段内的 id")
        # release 层：二道防线，非死代码。owner 整段已在上面按 profile 过滤后与
        # 保留集比对过一次——若那道检查健在，落在段内的单个 id 不可能撞账本，这里
        # 到不了 True 分支；留着是防那道检查将来被改坏时不至于连带丢了这层保护。
        # test 层：`profile != "test"` 这个前置条件不是防御性冗余，而是让 range 级
        # 豁免真正生效的必要条件——去掉它，test 层刚被允许撞账本的区段会在这里被
        # 逐 id 重新比对一遍，等于把上面放行的豁免原样撤销。此分支同样到不了
        # True，但那是这行代码故意做到的，不是巧合，也不是"留了个用不上的检查"。
        if profile != "test" and i in ledger_ids:
            raise OverlayError(f"{owner} 的 id {i} 与账本冲突")
        # 二道防线，非死代码：owner 区段两两不交对全部 profile 都生效（见上），
        # 同一个数字 id 因此不可能落进两个不同 owner 的声明区段——这条真正防的
        # 是同一个 owner 被 manifest["scripts"] 重复登记（同一文件两条 spec）
        # 这类配置错误，而不是「跨 owner 撞号」（那种情况会先被区段不交挡住）。
        if i in seen:
            raise OverlayError(f"id {i} 被 {seen[i]} 与 {owner} 同时使用")
        seen[i] = owner


import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone

#: lua 双引号字面串。`[^"\\\n]|\\.` 让转义引号留在串内，换行则终止——注释里的字不算。
_LUA_STR_RE = _re.compile(r'"((?:[^"\\\n]|\\.)*)"')


def charset_of(sources: list[str], ledger_jp: list[str], always: list[int]) -> list[int]:
    """字集 = 最终源的字面串 ∪ 账本 jp ∪ 常驻表，过滤到 BMP 可见区。

    保留账本 jp 是「宁滥勿缺」：未译面仍要渲染日文，且这样今日字集恒为新字集的
    子集，字体只会变大不会漏字。
    """
    chars: set[int] = set(always)
    for src in sources:
        for lit in _LUA_STR_RE.findall(src):
            chars.update(ord(c) for c in lit)
    for jp in ledger_jp:
        chars.update(ord(c) for c in jp)
    return sorted(c for c in chars if 0x20 <= c <= 0xFFFF)


def write_charset(codes: list[int], path: Path) -> None:
    """写 ttf_pgf 要的码位表：一行一个四位小写十六进制。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"{c:04x}\n" for c in codes), encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "absent"


def _tree_sha256(root: Path) -> str:
    """给一整棵目录树算确定性哈希：按相对路径升序遍历 `*.lua`，把「路径 + 内容」
    一起喂进摘要，不存在则按 `_sha256` 的约定返回 "absent"（取证失败不阻断构建）。

    路径必须入摘要，不能只喂内容——否则一次纯改名（字节不变，换反编译基座时
    常见）在这份指纹里完全隐身，而改名同样是必须被看见的输入变化。逐条记录
    用一个空字节隔开路径与内容、一个换行符隔开不同文件，避免拼接后前一条的
    内容尾部与后一条的路径头部产生歧义。
    """
    if not root.exists():
        return "absent"
    h = hashlib.sha256()
    names = sorted(p.relative_to(root).as_posix()
                   for p in root.rglob("*.lua") if p.is_file())
    for name in names:
        h.update(name.encode("utf-8"))
        h.update(b"\0")
        h.update((root / name).read_bytes())
        h.update(b"\n")
    return h.hexdigest()


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=REPO, capture_output=True,
                              text=True, check=True).stdout.strip()
    except Exception:                     # noqa: BLE001 — 取证失败不该阻断构建
        return ""


def provenance(profile: str, manifest: dict, root: Path, applied: list[dict],
               scripts_added: list[str], members: dict, outputs: dict) -> dict:
    """构建取证：输入与工具的哈希、git 状态、本次施加的层。"""
    lane = REPO / manifest["lane"]["dir"]
    inputs = {}
    for rel in ("forward.jsonl", "patches.jsonl", "forward_extra.jsonl"):
        inputs[str((lane / rel).relative_to(REPO))] = _sha256(lane / rel)
    for key in ("ledger", "ledger_extra"):
        p = REPO / manifest["base"][key]
        inputs[manifest["base"][key]] = _sha256(p)
    for p in sorted(root.rglob("*")):
        if p.is_file():
            # 用 root.parent 而不是 REPO：真实调用里 root=LAYERS=REPO/"layers"，
            # 两者等价；但测试传的是 tmp_path 下的层根，不在 REPO 子树内，
            # relative_to(REPO) 会当场 ValueError——取证函数不该因为调用方是
            # 测试夹具就崩溃，键的相对基准应随 root 自己走。
            inputs[str(p.relative_to(root.parent))] = _sha256(p)
    # 基座本身也要入指纹——换反编译基座（migrate_base.py 重跑）不改车道/账本，
    # 但改的正是「哪些 lua 字节被编译进盘」，漏了它两次不同基座的构建会指纹撞车。
    base_dir = manifest["base"]["dir"]
    inputs[base_dir] = _tree_sha256(REPO / base_dir)
    # SNDL_LUAC / SNDL_TTF_PGF：与 tools/inject_lua.py、tools/build_font.py 同一惯例
    # （环境变量覆盖，manifest / 硬编码默认路径兜底）。ttf_pgf 平时活在 /tmp 下，
    # 重启即失，构建者常须重新指到别处；不认这个环境变量，"absent" 记的就是假话——
    # 工具明明被用了，取证却说它不在。
    luac = Path(os.environ.get("SNDL_LUAC", manifest["compiler"]["luac"])).expanduser()
    ttf_pgf = Path(os.environ.get("SNDL_TTF_PGF", "/tmp/pgftool/ttf_pgf"))
    return {
        "profile": profile,
        "built_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "git": {"head": _git("rev-parse", "HEAD"),
                "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
                "dirty": [l[3:] for l in _git("status", "--short").splitlines()]},
        "inputs": inputs,
        "tools": {"luac_sz4": _sha256(luac),
                  "ttf_pgf": _sha256(ttf_pgf)},
        "layers_applied": [{"overlay": o["_name"], "target": o["target"],
                            "ops": len(o["ops"])} for o in applied],
        "scripts_added": scripts_added,
        "members": members,
        "outputs": outputs,
    }


def write_provenance(prov: dict, path: Path) -> None:
    """把 `provenance()` 的返回值落盘成带缩进的 UTF-8 JSON（中文原样，不转义）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(prov, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

