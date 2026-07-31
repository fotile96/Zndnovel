import json
import os
import subprocess
import sys
from pathlib import Path
from tools.pipelib import dumps, read_jsonl, append_jsonl, write_jsonl, display_width, sha256_file, REPO

def test_dumps_keeps_unicode_and_is_compact():
    assert dumps({"jp": "彩野さん", "n": 1}) == '{"jp":"彩野さん","n":1}'

def test_jsonl_roundtrip_and_append(tmp_path):
    p = tmp_path / "a.jsonl"
    write_jsonl(p, [{"id": 1}, {"id": 2}])
    append_jsonl(p, [{"id": 3}])
    assert [r["id"] for r in read_jsonl(p)] == [1, 2, 3]

def test_display_width_east_asian():
    assert display_width("あa") == 3
    assert display_width("【彩野】「うん」") == 16

def test_sha256_file(tmp_path):
    p = tmp_path / "x.bin"; p.write_bytes(b"abc")
    assert sha256_file(p) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"

def test_repo_points_at_project_root():
    assert (REPO / "lua_scripts").is_dir()

def test_zn_env_vars_override_data_and_work(tmp_path):
    """Critical 1：ZND_DATA/ZND_WORK 环境变量覆盖 DATA/WORK（REPO 不受影响）——
    这是让 subprocess 形式跑的 tools/*.py 变 hermetic 的唯一通道。用真实子进程
    （而非 importlib.reload）验证，因为 DATA/WORK 是模块导入时求值一次的常量，
    同进程内后设 os.environ 不会生效，只有"新进程 import 前设好环境变量"才作数
    ——这恰是 test_e2e_dryrun.py 实际依赖的机制。去掉 os.environ.get(...) 那层
    （改回裸 REPO/"data"、REPO/"work"）此测试必红。"""
    want_data, want_work = tmp_path / "d", tmp_path / "w"
    r = subprocess.run(
        [sys.executable, "-c", "from tools.pipelib import DATA, WORK, REPO; "
                                "print(DATA); print(WORK); print(REPO)"],
        cwd=REPO, capture_output=True, text=True,
        env={**os.environ, "ZND_DATA": str(want_data), "ZND_WORK": str(want_work)})
    assert r.returncode == 0, r.stderr
    data_line, work_line, repo_line = r.stdout.splitlines()
    assert data_line == str(want_data)
    assert work_line == str(want_work)
    assert repo_line == str(REPO)          # REPO 本身不受这两个变量影响

def test_zn_env_vars_default_to_repo_subdirs_when_unset():
    """未设置 ZND_DATA/ZND_WORK 时，DATA/WORK 必须还是 REPO/"data"、REPO/"work"
    （env 覆盖是加性的，不设置时行为不变）。"""
    env = {k: v for k, v in os.environ.items() if k not in ("ZND_DATA", "ZND_WORK")}
    r = subprocess.run(
        [sys.executable, "-c", "from tools.pipelib import DATA, WORK, REPO; "
                                "print(DATA); print(WORK)"],
        cwd=REPO, capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    data_line, work_line = r.stdout.splitlines()
    assert data_line == str(REPO / "data")
    assert work_line == str(REPO / "work")
