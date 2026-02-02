import os
import json
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

import app.config as config
from app.scanner import Scanner

app = FastAPI()

# Монтируем статику
app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/")
async def root():
    return FileResponse("frontend/index.html")

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()

    print("connection open")

    # Создаём локальный сканер, привязанный к этому WebSocket
    local_scanner = Scanner(ws)

    # Если это первое подключение — сохраняем как активный
    if not config.scanner_active:
        config.scanner_active = True
        config.active_scanner = local_scanner

    # Запускаем сканер для этого клиента
    asyncio.create_task(local_scanner.run())

    # Отправляем начальный статус и конфиг
    try:
        await ws.send_json({"type": "status", "active": True})
        await ws.send_json({"type": "config", "config": config.current_config.dict()})
    except:
        print("Ошибка при отправке статуса/конфига")

    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)
            act = msg.get("action", "")

            if act == "clear":
                local_scanner.signals = []
                if ws.client_state.name == "CONNECTED":
                    await ws.send_json({"type": "clear"})

            elif act == "update_config":
                config.current_config = config.Config(**msg["config"])
                if ws.client_state.name == "CONNECTED":
                    await ws.send_json({"type": "config", "config": config.current_config.dict()})

            elif act == "get_config":
                if ws.client_state.name == "CONNECTED":
                    await ws.send_json({"type": "config", "config": config.current_config.dict()})

    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        print(f"WebSocket error: {e}")

if __name__ == "__main__":
    if not os.path.isdir("frontend"):
        raise RuntimeError("Папка frontend не найдена")
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8080, reload=True)
