"""local_assets：基座保真与全量编译。缺 luac_sz4 或原包解包镜像即整体 skip。"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from tools.layers import REPO, build_final_sources, load_manifest
from tools.luac_norm import compare_dirs

_MANIFEST = load_manifest()
# 与 tools/layers.py 的 provenance()/_compare_compiled() 同一惯例：SNDL_LUAC 覆盖
# manifest 里的硬编码默认路径。少了这行的后果不是「测试也跳」那么温和——是反过来：
# 在一台只靠 SNDL_LUAC 才找得到编译器的机器上，本文件这个全库最强的保真测试会
# 判定「缺 luac」而 skip，CLI 的 `layers.py check --compare-compiled`（同样吃
# SNDL_LUAC）却能正常跑——最该跑的测试反而没跑，且没有任何提示。
LUAC = Path(os.environ.get("SNDL_LUAC") or "~/pyluadec-refactor/build/luac_sz4").expanduser()
CORPUS = Path("~/pyluadec-refactor/corpus/final").expanduser()
DATABIN_SCRIPT = REPO / "build" / "databin" / "script"
# 头部签名已经在 layers/manifest.toml 的 [compiler] 里声明过一次，这里不重复写死
# 第二份——两处一旦分叉（比如换了编译器版本），硬编码的这份不会跟着更新。
PSP_LUAC_HEADER = bytes.fromhex(_MANIFEST["compiler"]["header_hex"])

pytestmark = [
    pytest.mark.local_assets,
    pytest.mark.skipif(not LUAC.exists(), reason=f"缺 {LUAC}"),
    pytest.mark.skipif(not DATABIN_SCRIPT.is_dir(),
                       reason="缺 build/databin（先 databin.py unpack）"),
]


def _compile_all(sources: dict[str, str], out: Path) -> list[str]:
    out.mkdir(parents=True, exist_ok=True)
    bad = []
    for name, text in sorted(sources.items()):
        src = out / ("_" + name)
        src.write_text(text, encoding="utf-8")
        dst = out / name
        proc = subprocess.run([str(LUAC), "-s", "-o", str(dst), str(src)],
                              capture_output=True, text=True)
        if proc.returncode != 0:
            bad.append(f"{name}: {proc.stderr.strip()}")
        elif dst.read_bytes()[:12] != PSP_LUAC_HEADER:
            bad.append(f"{name}: 头非 PSP ABI")
        src.unlink()
    return bad


def test_base_is_byte_identical_to_original_bytecode():
    """基座重编译、行号归零后必须与原包字节码逐字节相同——229/229。"""
    with tempfile.TemporaryDirectory() as td:
        base = {p.name: p.read_text(encoding="utf-8")
                for p in sorted((REPO / "lua_scripts").glob("*.lua"))}
        bad = _compile_all(base, Path(td))
        assert not bad, f"基座有文件编译失败：{bad[:3]}"
        same, diff, err, names = compare_dirs(Path(td), DATABIN_SCRIPT)
        assert (diff, err) == (0, 0), f"基座不再与原字节码等价：{names[:5]}"
        assert same == 229, f"只比对了 {same} 个文件"


def test_migrate_base_check_passes():
    if not CORPUS.is_dir():
        pytest.skip(f"缺 {CORPUS}")
    r = subprocess.run([sys.executable, "tools/migrate_base.py", "--check"],
                       cwd=REPO, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_release_final_sources_all_compile():
    sources, _, added = build_final_sources("release")
    assert "snr_finale.lua" in sources
    with tempfile.TemporaryDirectory() as td:
        bad = _compile_all(sources, Path(td))
    assert not bad, f"最终源编译失败：{bad[:3]}"
