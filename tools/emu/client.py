"""PPSSPP WebSocket 调试器异步客户端（模拟器 e2e 管线的核心库）。

协议（PPSSPP 源码 docs/WebSocketDebugger.md，master 1ee9168 实测）：
  - ws://host:port/debugger，子协议 debugger.ppsspp.org（必须），JSON 双向 {"event": ...}。
  - 请求带 ticket 则响应回带同名 event + ticket；错误统一 {"event":"error", "message", "level", ticket}。
  - 无 ticket 的入站消息是广播（log / game.* / cpu.stepping / cpu.resume /
    cpu.breakpoint.hit / input.buttons / input.analog）。
  - 这些请求不直接回包、结果以广播到达：cpu.resume、cpu.stepInto/Over/Out、
    cpu.runUntil、cpu.runUntilTime、cpu.nextHLE、cpu.stepping、gpu.stats.feed
    ——对它们用 fire() + wait_broadcast()。
  - input.buttons.press 例外：按满 duration 帧后才回包（本身即同步原语）。
"""
from __future__ import annotations

import asyncio
import base64
import binascii
import collections
import itertools
import json
from typing import Any, Callable

import websockets

SUBPROTOCOL = "debugger.ppsspp.org"
# PSP 按键名全集见 InputSubscriber.cpp；常用子集列在这里作拼写防呆。
BUTTONS = {
    "cross", "circle", "triangle", "square", "up", "down", "left", "right",
    "start", "select", "home", "ltrigger", "rtrigger",
}


class EmuError(RuntimeError):
    """PPSSPP 返回的 error 事件。level 语义：1=NOTICE 2=ERROR 3=WARN 4=INFO 5=DEBUG。"""

    def __init__(self, message: str, level: int | None = None):
        super().__init__(message)
        self.level = level


class EmuClient:
    def __init__(self, port: int, host: str = "127.0.0.1", name: str = "zndnovel-emu"):
        self.host, self.port, self.name = host, port, name
        self.server_info: dict | None = None  # version 握手响应（含 pid/path）
        self._ws = None
        self._reader_task: asyncio.Task | None = None
        self._tickets = itertools.count(1)
        self._pending: dict[int, asyncio.Future] = {}
        self._history: collections.deque[dict] = collections.deque(maxlen=8192)
        self._seq = 0  # 广播总数（含被 deque 挤掉的），wait_broadcast 用它做游标
        self._new_broadcast = asyncio.Event()

    # ---- 连接生命周期 -------------------------------------------------

    async def connect(self, retry_seconds: float = 15.0,
                      alive: Callable[[], bool] | None = None) -> "EmuClient":
        """建立连接并完成 version 握手。alive 回调返回 False 时提前放弃（进程已死）。"""
        uri = f"ws://{self.host}:{self.port}/debugger"
        deadline = asyncio.get_event_loop().time() + retry_seconds
        while True:
            try:
                self._ws = await websockets.connect(
                    uri, subprotocols=[SUBPROTOCOL], max_size=64 * 1024 * 1024)
                break
            except OSError:
                if alive is not None and not alive():
                    raise ConnectionError("PPSSPP 进程已退出，放弃连接")
                if asyncio.get_event_loop().time() >= deadline:
                    raise
                await asyncio.sleep(0.5)
        self._reader_task = asyncio.create_task(self._reader())
        self.server_info = await self.request("version", name=self.name, version="0.1")
        return self

    async def aclose(self) -> None:
        if self._reader_task is not None:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except (asyncio.CancelledError, Exception):
                pass
            self._reader_task = None
        if self._ws is not None:
            await self._ws.close()
            self._ws = None

    async def __aenter__(self) -> "EmuClient":
        return await self.connect()

    async def __aexit__(self, *exc) -> None:
        await self.aclose()

    async def _reader(self) -> None:
        async for raw in self._ws:
            data = json.loads(raw)
            ticket = data.get("ticket")
            fut = self._pending.pop(ticket, None) if ticket is not None else None
            if fut is not None and not fut.done():
                fut.set_result(data)
            else:
                self._history.append(data)
                self._seq += 1
                self._new_broadcast.set()

    # ---- 请求原语 -----------------------------------------------------

    async def request(self, event: str, *, timeout: float = 10.0, **params: Any) -> dict:
        ticket = next(self._tickets)
        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[ticket] = fut
        await self._ws.send(json.dumps({"event": event, "ticket": ticket, **params}))
        try:
            data = await asyncio.wait_for(fut, timeout)
        finally:
            self._pending.pop(ticket, None)
        if data.get("event") == "error":
            raise EmuError(data.get("message", "<无消息>"), data.get("level"))
        return data

    async def fire(self, event: str, **params: Any) -> None:
        """发送不直接回包的事件（cpu.resume 等）。"""
        await self._ws.send(json.dumps({"event": event, **params}))

    def seq_mark(self) -> int:
        """当前广播游标。配合 wait_broadcast(after_seq=...) 只匹配此后到达的广播。"""
        return self._seq

    async def wait_broadcast(self, event: str | None = None, *,
                             predicate: Callable[[dict], bool] | None = None,
                             after_seq: int | None = None,
                             timeout: float = 10.0) -> dict:
        """等待匹配的广播。默认也匹配历史（连接以来入队的），要排除陈旧事件
        （如开局 startBreak 的 cpu.stepping）就先 seq_mark() 再传 after_seq。"""
        def match(d: dict) -> bool:
            if event is not None and d.get("event") != event:
                return False
            return predicate is None or predicate(d)

        loop = asyncio.get_event_loop()
        deadline = loop.time() + timeout
        cursor = self._seq - len(self._history)  # 历史最老一条的全局序号
        if after_seq is not None:
            cursor = max(cursor, after_seq)
        while True:
            base = self._seq - len(self._history)
            for i in range(max(cursor - base, 0), len(self._history)):
                if match(self._history[i]):
                    cursor = base + i + 1
                    return self._history[i]
            cursor = self._seq
            remaining = deadline - loop.time()
            if remaining <= 0:
                raise TimeoutError(f"等待广播超时: event={event}")
            self._new_broadcast.clear()
            try:
                await asyncio.wait_for(self._new_broadcast.wait(), remaining)
            except asyncio.TimeoutError:
                raise TimeoutError(f"等待广播超时: event={event}") from None

    def drain_broadcasts(self, event: str | None = None) -> list[dict]:
        """非阻塞取走当前历史里匹配的广播（用于收尾断言，如汇总 log）。"""
        out = [d for d in self._history if event is None or d.get("event") == event]
        return out

    # ---- 常用命令封装 -------------------------------------------------

    async def game_status(self) -> dict:
        return await self.request("game.status")

    async def cpu_status(self) -> dict:
        return await self.request("cpu.status")

    async def resume(self) -> None:
        await self.fire("cpu.resume")

    async def break_cpu(self, timeout: float = 10.0) -> dict:
        """请求 CPU 进入断住态。已经断住时直接返回——那种情况不会再有新广播，
        傻等 cpu.stepping 必然超时（2026-08-31 playthrough 实测踩到）。"""
        status = await self.cpu_status()
        if status.get("stepping"):
            return status
        mark = self.seq_mark()
        await self.fire("cpu.stepping")
        try:
            return await self.wait_broadcast("cpu.stepping", after_seq=mark, timeout=timeout)
        except TimeoutError:
            status = await self.cpu_status()
            if status.get("stepping"):
                return status          # 广播丢了但状态已到位
            raise

    async def run_until_time(self, relative_us: int, timeout: float = 30.0) -> dict:
        """跑指定模拟时长后断住（master 专属 cpu.runUntilTime）。"""
        mark = self.seq_mark()
        await self.fire("cpu.runUntilTime", relativeUs=relative_us)
        return await self.wait_broadcast("cpu.stepping", after_seq=mark, timeout=timeout)

    async def read_bytes(self, address: int, size: int) -> bytes:
        data = await self.request("memory.read", address=address, size=size)
        return base64.b64decode(data["base64"])

    async def read_u32(self, address: int) -> int:
        return (await self.request("memory.read_u32", address=address))["uintValue"]

    async def read_string(self, address: int) -> str:
        return (await self.request("memory.readString", address=address))["value"]

    async def write_bytes(self, address: int, blob: bytes) -> None:
        await self.request("memory.write", address=address,
                           base64=binascii.b2a_base64(blob, newline=False).decode())

    async def disasm(self, address: int, count: int) -> list[dict]:
        data = await self.request("memory.disasm", address=address, count=count,
                                  displaySymbols=False)
        return data["lines"]

    async def bp_add(self, address: int, *, enabled: bool = True, log: bool = False,
                     condition: str | None = None, log_format: str | None = None) -> None:
        params: dict[str, Any] = {"address": address, "enabled": enabled, "log": log}
        if condition is not None:
            params["condition"] = condition
        if log_format is not None:
            params["logFormat"] = log_format
        await self.request("cpu.breakpoint.add", **params)

    async def bp_remove(self, address: int) -> None:
        await self.request("cpu.breakpoint.remove", address=address)

    async def buttons_send(self, buttons: dict[str, bool]) -> None:
        unknown = set(buttons) - BUTTONS
        assert not unknown, f"未知按键名: {unknown}"
        await self.request("input.buttons.send", buttons=buttons)

    async def buttons_press(self, button: str, duration: int = 1) -> None:
        """按 duration 帧后自动松开；回包在松开之后到达（同步原语）。"""
        assert button in BUTTONS, f"未知按键名: {button}"
        await self.request("input.buttons.press", button=button, duration=duration,
                           timeout=duration / 60.0 + 10.0)

    async def analog_send(self, x: float, y: float, stick: str = "left") -> None:
        await self.request("input.analog.send", x=x, y=y, stick=stick)

    async def screenshot(self) -> tuple[bytes, int, int]:
        """当前画面 PNG（gpu.buffer.screenshot，'uri' 形态）。返回 (png_bytes, w, h)。

        ⚠ 本机实测（macOS，master 1ee9168）：CPU 断住时该命令在 software 与
        Vulkan 后端都答 "Could not download output"（GE 线程不服务回读）——
        游戏截图请改用 vram_screenshot()。保留本方法以备上游修复。"""
        data = await self.request("gpu.buffer.screenshot", type="uri", timeout=30.0)
        uri = data["uri"]
        prefix = "base64,"
        png = base64.b64decode(uri[uri.index(prefix) + len(prefix):])
        return png, data["width"], data["height"]

    VRAM_FB0 = 0x04000000  # PSP 显存基址；引擎双缓冲的另一块常在 +0x88000
    VRAM_FB1 = 0x04088000

    async def vram_screenshot(self, address: int = VRAM_FB0, *, width: int = 480,
                              height: int = 272, stride: int = 512):
        """软渲染下直读模拟 VRAM 帧缓冲，返回 PIL Image（RGB，width×height）。

        前提：--graphics=software（帧缓冲真实驻留模拟 VRAM）且 CPU 已断住
        （break_cpu）。像素即软渲染确定性输出，比后端回读更适合 golden diff。
        格式按本作实测 RGBA8888/stride 512 处理。"""
        from PIL import Image  # 延迟导入，保持客户端库对 Pillow 弱依赖
        raw = await self.read_bytes(address, stride * height * 4)
        img = Image.frombytes("RGBA", (stride, height), raw).convert("RGB")
        return img.crop((0, 0, width, height))

    async def speed_set(self, *, fast_forward: bool | None = None,
                        percent: int | None = None) -> dict:
        """远程调速（master 专属 game.speed.set）。"""
        params: dict[str, Any] = {}
        if fast_forward is not None:
            params["fastForward"] = fast_forward
        if percent is not None or fast_forward is None:
            params["percent"] = percent
        return await self.request("game.speed.set", **params)
