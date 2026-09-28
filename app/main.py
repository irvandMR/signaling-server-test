from app.core.config import Settings
from app.controller.api import fastapi_app
from app.socket.sockets import sio
import socketio
import uvicorn

app = socketio.ASGIApp(sio, other_asgi_app=fastapi_app)

if __name__ == "__main__":
    uvicorn.run(Settings.RUN_APP, host=Settings.HOST, port=Settings.PORT, reload=True)
