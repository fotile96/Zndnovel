"""PPSSPP 1.20.x（iOS 商店版同版本）的驾驶会话。

该版 SDL 构建没有 --debugger= 参数，远程调试器只能由 ini 的 RemoteDebuggerOnStartup + RemoteISOPort
打开（端口因此是固定的）；软渲染同样经 ini。进入时改 ini、退出时原样写回。
二进制缺省 ~/ppsspp-1204/build/PPSSPPSDL.app（本机 v1.20.4 构建），SNDL_PPSSPP_1204 覆盖。
依据：docs/ops/movie-playback-ppsspp-2026-09-24.md「追记：iOS」。
"""
from __future__ import annotations

import contextlib
import os
import re
import socket
import subprocess
import time
from pathlib import Path

from tools.emu.client import EmuClient

APP = Path(os.environ.get("SNDL_PPSSPP_1204",
                          Path.home() / "ppsspp-1204/build/PPSSPPSDL.app/Contents/MacOS/PPSSPPSDL"))
INI = Path.home() / ".config/ppsspp/PSP/SYSTEM/ppsspp.ini"
LOG_DIR = Path(__file__).resolve().parents[2] / "build" / "emu" / "logs"


def _set(text: str, key: str, val: str) -> str:
    new, n = re.subn(rf"^{key} = .*$", f"{key} = {val}", text, flags=re.M)
    if n != 1:
        raise RuntimeError(f"ppsspp.ini 里找不到唯一的 {key}")
    return new


def _port_taken(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


@contextlib.asynccontextmanager
async def session(disc: Path, *, app: Path = APP, port: int = 45699, core: int | None = None,
                  start_break: bool = False, extra: dict[str, str] | None = None):
    """产出 (proc, EmuClient, 日志路径)。core：CPUCore（0 解释器 / 1 JIT / 2 IR 解释器）；
    start_break：AutoRun=False，开机即停。"""
    if not Path(app).exists():
        raise RuntimeError(f"找不到 PPSSPP 1.20.x 二进制：{app}（SNDL_PPSSPP_1204 可覆盖）")
    if _port_taken(port):
        raise RuntimeError(f"端口 {port} 已被占用（上一轮的 PPSSPP 没退？）——固定端口会连错进程")
    orig = INI.read_text(encoding="utf-8")
    t = orig
    for k, v in {"RemoteDebuggerOnStartup": "True", "RemoteISOPort": str(port),
                 "GraphicsBackend": "0 (OPENGL)", "SoftwareRenderer": "True", **(extra or {})}.items():
        t = _set(t, k, v)
    if core is not None:
        t = _set(t, "CPUCore", str(core))
    if start_break:
        t = _set(t, "AutoRun", "False")
    INI.write_text(t, encoding="utf-8")
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logp = LOG_DIR / f"{time.strftime('%H%M%S')}-app1204.log"
    proc = None
    try:
        with open(logp, "w") as lf:
            proc = subprocess.Popen([str(app), str(Path(disc).resolve())], stdout=lf, stderr=subprocess.STDOUT)
        cli = EmuClient(port=port)
        await cli.connect(retry_seconds=20, alive=lambda: proc.poll() is None)
        try:
            yield proc, cli, logp
        finally:
            await cli.aclose()
    finally:
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(3)
        INI.write_text(orig, encoding="utf-8")
