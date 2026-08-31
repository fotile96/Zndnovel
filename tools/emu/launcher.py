"""PPSSPP 进程启动器：headless / app 两种构建的生命周期管理。

约定（docs/ops/ppsspp-local-setup-2026-08-31.md 验收的坑）：
  - headless 引导路径必须绝对路径（相对裸文件名触发 host0: 挂载 bug）；
  - 本机无 Vulkan 库，一律显式 --graphics=software（软渲染也是像素确定性首选）；
  - --debugger=<port> 非零端口是强制绑定，占用即退出 → 冲突时换端口重试；
  - headless 下 --debugger 会开局断住 CPU（先埋断点再放行的窗口）。

二进制路径可用环境变量覆盖：SNDL_PPSSPP_HEADLESS / SNDL_PPSSPP_APP。
"""
from __future__ import annotations

import contextlib
import os
import random
import subprocess
import time
from pathlib import Path

from tools.emu.client import EmuClient

REPO = Path(__file__).resolve().parent.parent.parent
LOG_DIR = REPO / "build" / "emu" / "logs"
TESTDATA = REPO / "build" / "emu" / "testdata"

HEADLESS_EXE = Path(os.environ.get(
    "SNDL_PPSSPP_HEADLESS",
    Path.home() / "ppsspp" / "build-headless" / "PPSSPPHeadless"))
APP_EXE = Path(os.environ.get(
    "SNDL_PPSSPP_APP",
    Path.home() / "ppsspp" / "build" / "PPSSPPSDL.app" / "Contents" / "MacOS" / "PPSSPPSDL"))


class Emulator:
    """单个 PPSSPP 进程。用 headless()/app() 工厂构造，start()/stop() 或 with 管理。"""

    def __init__(self, exe: Path, args: list[str], *, port: int | None = None, tag: str = "emu"):
        self.exe, self.extra_args, self.tag = Path(exe), args, tag
        self.port = port or random.randrange(20000, 60000)
        self.proc: subprocess.Popen | None = None
        self.log_path: Path | None = None

    @classmethod
    def headless(cls, boot: Path | str, *, graphics: str = "software",
                 timeout_s: int = 120, log_all: bool = True, port: int | None = None,
                 extra: tuple[str, ...] = ()) -> "Emulator":
        boot = Path(boot).resolve()
        assert boot.exists(), f"引导文件不存在: {boot}"
        # -l 开全量日志：断点 logFormat 走 NOTICE_LOG(Log::JIT)，不开则 WS log 广播收不到
        args = [str(boot), f"--graphics={graphics}", f"--timeout={timeout_s}", *extra]
        if log_all:
            args.append("-l")
        return cls(HEADLESS_EXE, args, port=port, tag=boot.stem)

    @classmethod
    def app(cls, boot: Path | str | None = None, *, graphics: str | None = "software",
            port: int | None = None, extra: tuple[str, ...] = ()) -> "Emulator":
        args = list(extra)
        if graphics is not None:
            args.append(f"--graphics={graphics}")
        if boot is not None:
            boot = Path(boot).resolve()
            assert boot.exists(), f"引导目标不存在: {boot}"
            args.append(str(boot))
        return cls(APP_EXE, args, port=port, tag="app")

    def start(self) -> "Emulator":
        assert self.exe.exists(), (
            f"找不到 PPSSPP 二进制: {self.exe}（可用 SNDL_PPSSPP_* 环境变量指定）")
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        self.log_path = LOG_DIR / f"{time.strftime('%H%M%S')}-{self.tag}-{self.port}.log"
        cmd = [str(self.exe), f"--debugger={self.port}", *self.extra_args]
        with open(self.log_path, "w") as log:
            log.write(f"# {' '.join(cmd)}\n")
            log.flush()
            self.proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
        return self

    def alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def wait_exit(self, timeout: float = 60.0) -> int:
        return self.proc.wait(timeout)

    def log_text(self) -> str:
        return self.log_path.read_text(errors="replace") if self.log_path else ""

    def stop(self) -> None:
        if self.alive():
            self.proc.terminate()
            try:
                self.proc.wait(3)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(3)

    def __enter__(self) -> "Emulator":
        return self.start()

    def __exit__(self, *exc) -> None:
        self.stop()


@contextlib.asynccontextmanager
async def session(make_emulator, *, connect_seconds: float = 15.0, retries: int = 3):
    """启动模拟器并连上调试器；端口被占（进程秒退）时换端口重试。

    make_emulator: 无参工厂，返回未 start 的 Emulator（每次重试重新构造以换端口）。
    产出 (Emulator, EmuClient)。
    """
    last_exc: Exception | None = None
    for _ in range(retries):
        emu = make_emulator().start()
        client = EmuClient(port=emu.port)
        try:
            await client.connect(retry_seconds=connect_seconds, alive=emu.alive)
        except (ConnectionError, OSError) as exc:
            last_exc = exc
            emu.stop()
            continue
        try:
            yield emu, client
        finally:
            await client.aclose()
            emu.stop()
        return
    raise ConnectionError(
        f"连续 {retries} 次未能连上调试器（最后错误: {last_exc}；日志见 {LOG_DIR}）")
