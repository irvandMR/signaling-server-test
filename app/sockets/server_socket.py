import socketio
from typing import Dict

# 1. Inisialisasi AsyncServer Socket.IO tunggal
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*"
)

# 2. Peta user online: { extension: sid }
online: Dict[str, str] = {}

# 3. Import handler agar event @sio.event teregistrasi ke instance sio
import sockets.handler_socket  # noqa: F401
