"""校验 `glossary/voices/*.md` 的示范译例与 `skeleton/anchors.yaml` 的定稿是否
自洽（机械闸，非漂移哈希比对——直接读内容比对）。

## 为什么需要这道闸

`anchors.yaml` 是用户终审定稿、逐字锁定的伏笔锚点基准——`glossary/style.md` 明写
「正文轨遇锚点 id 一律逐字沿用锚点 zh，即使与更忠实的直译冲突」。`voices/*.md`
的「例句（日→中）」小节里，部分示范译例标了 vms 消息 id；若这个 id 恰好也是
anchors 收录的锚点，两处 zh 就必须逐字一致，否则就是"一份冻结件在教译者违背
另一份冻结件"。SEG-4 生产会话曾用过宽的判据（"锚点全串是否整体出现在 voices
里"）误报 44/76 条不符（voices 大量条目只引片段，整串匹配注定落空）；换成本
文件这套精确判据后，真实语料上只查出 4 条真冲突（已由控制器手工改掉 voices，
因为 anchors 是终审定稿，不可反向修正）。

## 判据（只挑"能确定对应单一锚点 id"的条目，宁可漏判也不可错判）

voices/*.md 的「例句」小节固定用两行体：
    N. [id]（可选：说话人/场景标签，日文引用……）
       → 【说话人】「中文译文」
本模块只认这一种形态：
  1. 某一行里 `\\[(\\d+)\\]` 恰好命中一次——多个 id 挤在同一行（如
     "[7396][7397]"、或"……（对方回敬 [3963]……）"这种夹带第二个 id 的注释）
     是多句合译或旁注引用，无法安全拆分对应到单一 zh，一律跳过；
  2. 且**紧邻的下一行** lstrip 后以 "→" 开头——不去追第三行（部分条目是
     "id 行 / 日文原文另起一行 / → 译文" 的三行体，如 naoya.md 例 1 的 6085；
     跳过是刻意的：一旦要跨行回溯就必须处理"这几行之间有没有混进别的 id"这类
     歧义，而当前语料下唯一因此漏掉的条目本就在 anchors 里完全一致，纳入与否
     不改变真实结论，不值得为之扩大判据面）；
  3. 该 id 必须能在 anchors.yaml 里查到，否则没有比对对象，不算「可比条目」
     （只是"这条例句引的 id 恰好不是锚点"，不是冲突，不报）。

## 为什么不把「行内引用」也纳入

语料里还有第三种引用形态：嵌在表格单元格 / 说明段落里的行内引用
`[id]「日文」→「中文」`（如 ayano_real.md 「[16382]「直哉……くん？」→「直哉…
…君？」」）。实测这类行内引用命中 anchors 的唯一一例是 yukari.md 的 [3962]：
该行内译文是「「啊，不良少年」」（表格行里说话人已由行首列名担当，故省略），
而 anchors 该条 zh 固定带前缀「【ユカリ】「啊，不良少年」」——按原样字符串比对
会把这纯粹的格式差异（有没有【说话人】前缀）误判成翻译冲突，正是 SEG-4 教训
（"判据过宽会用伪报淹没真信号"）要防的事。要安全纳入就得先做"剥离说话人前缀
再比"的归一化，但归一化本身可能真的吃掉说话人错位这类实质冲突，而语料里目前
只多验 1 条、且已知其内容一致——收益不足以抵消这层复杂度，故本版本不纳入，
只做两行体的精确匹配。（若未来该形态命中数变多，值得单独评估再决定要不要加。）
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import REPO

_ID_RE = re.compile(r"\[(\d+)\]")


def load_anchors(anchors_path) -> dict:
    """anchors.yaml 的真实 schema 是 `[{chapter, items: [{id, zh, ...}]}]` 嵌套，
    不是平铺列表——早前生产会话曾按平铺解析导致恒返回 0 命中（"结论没错、方法
    错了"），此处务必按嵌套结构取，id -> zh。"""
    import yaml
    doc = yaml.safe_load(Path(anchors_path).read_text(encoding="utf-8")) or []
    out = {}
    for chapter in doc:
        for item in chapter.get("items", []):
            out[item["id"]] = item["zh"]
    return out


def extract_citations(md_path):
    """从一份 voices/*.md 抽取"两行体"示范译例，返回 (行号, id, voices_zh) 列表。
    行号 1-based，指向 "→" 所在的那一行（报错时直接定位到译文本身）。"""
    lines = Path(md_path).read_text(encoding="utf-8").splitlines()
    out = []
    for i in range(len(lines) - 1):
        ids = _ID_RE.findall(lines[i])
        if len(ids) != 1:
            continue
        nxt = lines[i + 1].lstrip()
        if not nxt.startswith("→"):
            continue
        zh = nxt[1:].strip()
        out.append((i + 2, int(ids[0]), zh))
    return out


def check(voices_dir, anchors_path):
    """比对 voices_dir 下全部 *.md 的可比条目与 anchors_path 定稿。

    返回 (mismatches, n_comparable)：
    - mismatches：每条冲突一行，含"文件:行号"、锚点 id、voices 写的、anchors
      定稿的——足以直接定位、直接判断该改哪边（正常应改 voices，anchors 是
      终审定稿）。
    - n_comparable：本次实际比对的条目数（诊断用：0 不代表"无冲突"，也可能是
      "判据没命中任何东西"，两者必须能区分）。
    """
    voices_dir, anchors_path = Path(voices_dir), Path(anchors_path)
    anchors = load_anchors(anchors_path)
    mismatches = []
    n_comparable = 0
    for md in sorted(voices_dir.glob("*.md")):
        for lineno, cid, voices_zh in extract_citations(md):
            if cid not in anchors:
                continue
            n_comparable += 1
            anchor_zh = anchors[cid]
            if voices_zh != anchor_zh:
                mismatches.append(
                    f"{md}:{lineno}: 锚点 id {cid} 冲突——voices 写「{voices_zh}」，"
                    f"anchors 定稿「{anchor_zh}」（anchors 为终审定稿，应改 voices）")
    return mismatches, n_comparable


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="校验 glossary/voices/*.md 示范译例与 skeleton/anchors.yaml "
                    "定稿是否自洽（只读，无选项）。")
    ap.parse_args(argv)
    mismatches, n = check(REPO / "glossary" / "voices",
                          REPO / "skeleton" / "anchors.yaml")
    if mismatches:
        print("\n".join(mismatches))
        print(f"（共比对 {n} 条可比条目，{len(mismatches)} 条冲突）")
        return 1
    print(f"OK（共比对 {n} 条可比条目，0 条冲突）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
