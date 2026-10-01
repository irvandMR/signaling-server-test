import logging
import asyncio
import socketio
import urllib.parse

from app.service.user_service import authenticate_user_connect

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("signaling-service")

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")

connected: dict[str, str] = {}

@sio.event
async def connect(sid, environ, auth):
    log.info(f"Client {sid} mencoba connect...")
    
    auth_data = auth or {}
    
    query_string = environ.get("QUERY_STRING", "")
    query_params = urllib.parse.parse_qs(query_string)
    
    # 1. Ambil data dari auth payload klien atau query string
    extension = auth_data.get("user") or query_params.get("user", [None])[0]
    password = auth_data.get("password") or query_params.get("password", [None])[0]
    
    if not extension or not password:
        log.warning(f"Client {sid} ditolak: Data kredensial tidak lengkap.")
        raise socketio.exceptions.ConnectionRefusedError("Kredensial tidak lengkap")
        
    # 2. Lakukan pengecekan Login (Autentikasi) lewat Service
    new_token = await authenticate_user_connect(extension, password)
    
    if not new_token:
        log.warning(f"Client {sid} ditolak: Login gagal untuk user {extension}.")
        # Cara terbaik di Socket.IO: Tolak koneksi dan kirim pesan error (berupa dictionary)
        raise socketio.exceptions.ConnectionRefusedError({"error": "Username atau Password salah"})
        
    # 3. Jika lolos login, daftarkan sessionnya
    connected[extension] = sid
    log.info(f"Client {sid} BERHASIL login sebagai user {extension}")
    await sio.save_session(sid, {"extension": extension, "token": new_token})
    
    #
    # 5. Kirim balasan token ke klien langsung tanpa delay
    await sio.emit("connected", {
        "message": f"Login Sukses! Hallo {extension}",
        "new_token": new_token
    }, to=sid)

    return True

@sio.event
async def disconnect(sid):
    log.info(f"Client {sid} disconnected")
    for uid, sess_id in list(connected.items()):
        if sess_id == sid:
            del connected[uid]
            break

# ==========================================
# WEBRTC SIGNALING EVENTS (JALUR B)
# ==========================================

@sio.event
async def webrtc_offer(sid, data):
    """Menerima SDP Offer dari penelepon dan meneruskannya ke Asterisk"""
    
    # Ambil identitas (ekstensi & token) langsung dari sesi Socket yang tersimpan saat login
    session = await sio.get_session(sid)
    caller_extension = session.get("extension")
    server_token = session.get("token")
    
    if not caller_extension:
        return
        
    # VALIDASI IDENTITAS: Klien harus menyertakan token yang mereka dapatkan saat login!
    client_token = data.get("token")
    if client_token != server_token:
        log.warning(f"[{caller_extension}] Mencoba menelpon tapi Token salah/kadaluarsa!")
        await sio.emit("webrtc_status", {"error": "Akses Ditolak: Token tidak valid!"}, to=sid)
        return
        
    target = data.get("target")
    sdp = data.get("sdp")
    
    log.info(f"[{caller_extension}] Mengirim panggilan ke [{target}]")
    
    # 1. Panggil service Asterisk SIP Gateway
    from app.service.asterisk_service import originate_call_with_sdp
    response = await originate_call_with_sdp(caller_extension, target, sdp)
    
    # 2. Kembalikan respons (SDP Answer) ke penelepon
    if response.get("status") == "success":
        await sio.emit("webrtc_answer", {"sdp": response.get("sdp")}, to=sid)
    else:
        await sio.emit("webrtc_status", {"error": response.get("message")}, to=sid)

@sio.event
async def webrtc_ice_candidate(sid, data):
    """Meneruskan ICE Candidate ke Asterisk"""
    # Logika untuk mengirim trickle ICE ke Asterisk
    pass
