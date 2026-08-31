"""模拟器活体测试的共用门槛。

这些测试要起真实的 PPSSPPHeadless 进程（本机构建）+ pspautotests 替身二进制
（tools/emu/fetch_testdata.sh 下载）。缺哪样就整体 skip——环境不齐不是代码坏了
（与顶层 conftest 的字体缺失同一处置哲学）。云端/CI 无构建时自动全 skip，
不拖慢默认 pytest。选择性排除：pytest -m "not emu"。
"""
from __future__ import annotations

import os

import pytest

from tools.emu.launcher import HEADLESS_EXE, TESTDATA

requires_stack = pytest.mark.skipif(
    not (HEADLESS_EXE.exists() and (TESTDATA / "cpu_alu.prx").exists()),
    reason="缺 PPSSPPHeadless 构建或测试素材（先跑 tools/emu/fetch_testdata.sh）",
)

GAME_DIR = os.environ.get("SNDL_GAME_DIR", "")
requires_game = pytest.mark.skipif(
    not GAME_DIR,
    reason="SNDL_GAME_DIR 未设置（等游戏 ISO 解包目录到位）",
)
