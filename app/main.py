import os
import sys

# Tambahkan direktori 'app' ke sys.path agar import internal (sockets, core, routes, dll.)
# bekerja lancar baik saat uvicorn dijalankan dari root maupun dari dalam folder app.
app_dir = os.path.dirname(os.path.abspath(__file__))
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

import socketio
from sockets.server_socket import sio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.config import configs
from routes import api_router

app = FastAPI(title="Websocket Signaling Service")

# Konfigurasi CORS agar bisa diakses dari browser / file HTML tester
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Daftarkan Router
app.include_router(api_router)

# Bungkus dengan Socket.IO ASGIApp
socket_app = socketio.ASGIApp(socketio_server=sio, other_asgi_app=app)