from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["WebSocket"])

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("Client Terhubung")

    try:
        while True:
            data = await websocket.receive_text()
            print(f"Menerima : {data}")
            await websocket.send_text(f"Echo : {data}")
    except WebSocketDisconnect:
        print("Client Terputus")
