#!/usr/bin/env python3
"""PPSSPP WebSocket 调试器探针（环境验证用，e2e 客户端库的前身）。

用法：
  uv run --with websockets python tools/e2e/probe.py [--port 45678] [--listen 秒数]
  uv run --with websockets python tools/e2e/probe.py --send '{"event":"game.status"}'

前置：PPSSPP 以 --debugger=<port> 启动（master 构建），或设置里勾选
Allow remote debugger（端口 = Local Server Port）。

协议要点（docs/WebSocketDebugger.md）：
  - URL ws://127.0.0.1:<port>/debugger，子协议 debugger.ppsspp.org（必须）。
  - 双向 JSON {"event": ...}；请求带 ticket 则响应原样回带。
  - 连接后惯例先发 version 自报家门。
"""
import argparse
import asyncio
import json
import sys

import websockets


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=45678)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--send", action="append", default=[],
                    help="额外发送的 JSON 事件（可多次），在握手之后逐条发出")
    ap.add_argument("--listen", type=float, default=3.0,
                    help="收尾监听广播的秒数（log/game.* 等）")
    ap.add_argument("--retry", type=int, default=20,
                    help="连接重试次数（每秒一次，等模拟器起动）")
    args = ap.parse_args()

    uri = f"ws://{args.host}:{args.port}/debugger"
    ws = None
    for attempt in range(args.retry):
        try:
            ws = await websockets.connect(uri, subprotocols=["debugger.ppsspp.org"],
                                          max_size=32 * 1024 * 1024)
            break
        except OSError:
            if attempt == args.retry - 1:
                raise
            await asyncio.sleep(1)
    async with ws:
        print(f"# connected {uri} (subprotocol={ws.subprotocol})")

        async def send(obj: dict) -> None:
            print(f"-> {json.dumps(obj, ensure_ascii=False)}")
            await ws.send(json.dumps(obj))

        await send({"event": "version", "name": "zndnovel-probe", "version": "0.1", "ticket": 1})
        await send({"event": "game.status", "ticket": 2})
        await send({"event": "cpu.status", "ticket": 3})
        for i, raw in enumerate(args.send):
            obj = json.loads(raw)
            obj.setdefault("ticket", 100 + i)
            await send(obj)

        loop = asyncio.get_event_loop()
        deadline = loop.time() + args.listen
        while True:
            timeout = deadline - loop.time()
            if timeout <= 0:
                break
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=timeout)
            except asyncio.TimeoutError:
                break
            data = json.loads(msg)
            # 截图类响应带巨大 base64，摘要显示
            if isinstance(data.get("uri"), str) and len(data["uri"]) > 120:
                data["uri"] = data["uri"][:80] + f"...({len(data['uri'])} chars)"
            print(f"<- {json.dumps(data, ensure_ascii=False)[:500]}")
    print("# closed")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
