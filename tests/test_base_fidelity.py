"""local_assets：基座保真与全量编译。缺 luac_sz4 或原包解包镜像即整体 skip。"""
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from tools.layers import REPO, build_final_sources
from tools.luac_norm import compare_dirs

LUAC = Path("~/pyluadec-refactor/build/luac_sz4").expanduser()
CORPUS = Path("~/pyluadec-refactor/corpus/final").expanduser()
DATABIN_SCRIPT = REPO / "build" / "databin" / "script"

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
        elif dst.read_bytes()[:12] != bytes.fromhex("1b4c75615100010404040800"):
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
