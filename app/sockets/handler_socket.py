import uuid
import asyncio
import urllib.parse
from typing import Dict, Any, Optional
import socketio

try:
    from core.database import AsyncSessionLocal
    from service.auth_service import verify_socket_token
    from services.call_manager import CallManager
    from services.call_repo import get_call_log_by_id
    from sockets.server_socket import sio, online
    from sockets.fake_pool import FakePool, fake_pool
except ImportError:
    from app.core.database import AsyncSessionLocal
    from app.service.auth_service import verify_socket_token
    from app.services.call_manager import CallManager
    from app.services.call_repo import get_call_log_by_id
    from app.sockets.server_socket import sio, online
    from app.sockets.fake_pool import FakePool, fake_pool


# ---------------------------------------------------------------------------
# In-Memory Tracking Panggilan Aktif
# ---------------------------------------------------------------------------
# active_calls: { call_id: { "call_id": ..., "from_ext": ..., "to_number": ..., "sid": ... } }
active_calls: Dict[str, Dict[str, Any]] = {}

# extension_calls: { extension: call_id } -> Menjamin batas 1 call per extension
extension_calls: Dict[str, str] = {}


def cleanup_active_call(call_id: str, ext: Optional[str] = None):
    """
    Membersihkan record panggilan aktif dari in-memory storage setelah panggilan berakhir.
    """
    call_info = active_calls.pop(call_id, None)
    from_ext = ext or (call_info.get("from_ext") if call_info else None)
    if from_ext and extension_calls.get(from_ext) == call_id:
        extension_calls.pop(from_ext, None)


# ---------------------------------------------------------------------------
# Helper: Mengambil identitas otentik dari session server (BUKAN payload client)
# ---------------------------------------------------------------------------
async def get_authenticated_user(sid: str) -> Optional[Dict[str, Any]]:
    """
    Mengambil session terautentikasi berdasarkan socket ID.
    KEAMANAN: Jangan percaya field 'from' yang dikirim oleh client.
    Selalu ambil extension & user_id dari session server ini!
    """
    return await sio.get_session(sid)


# ---------------------------------------------------------------------------
# 1. Handler Event Connect
# ---------------------------------------------------------------------------
@sio.event
async def connect(sid: str, environ: dict, auth: Optional[dict] = None):
    # 1. Baca token dari auth payload (atau fallback query string jika ada)
    token = None
    if isinstance(auth, dict):
        token = auth.get("token")

    if not token and "QUERY_STRING" in environ:
        qs = dict(urllib.parse.parse_qsl(environ["QUERY_STRING"]))
        token = qs.get("token")

    # Tolak jika token tidak disertakan
    if not token:
        print(f"❌ [CONNECT REJECTED] SID {sid}: Token tidak disertakan")
        raise socketio.exceptions.ConnectionRefusedError("Token required")

    # 2. Verifikasi token ke database
    async with AsyncSessionLocal() as db:
        user_info = await verify_socket_token(db, token)
        if not user_info:
            print(f"❌ [CONNECT REJECTED] SID {sid}: Token tidak valid atau sudah dicabut")
            raise socketio.exceptions.ConnectionRefusedError("Authentication failed")

    ext = user_info["ext"]
    user_id = user_info["user_id"]

    # 3. Kebijakan 1 extension 1 socket: HP baru menendang HP lama
    if ext in online:
        old_sid = online[ext]
        if old_sid != sid:
            print(f"⚠️ [KICK] Ext {ext}: Menendang SID lama {old_sid} karena login baru dari SID {sid}")
            try:
                # Beritahu HP lama bahwa sesi telah digantikan
                await sio.emit(
                    "session:replaced",
                    {"message": "Akun Anda telah login di perangkat lain"},
                    to=old_sid
                )
                await sio.disconnect(old_sid)
            except Exception as e:
                print(f"Error disconnecting old sid {old_sid}: {e}")

    # 4. Simpan identitas asli ke session server (Hindari pemalsuan field 'from')
    await sio.save_session(sid, {
        "user_id": user_id,
        "ext": ext,
        "sip_ha1": user_info.get("sip_ha1")
    })

    # 5. Daftarkan ke peta online[ext] = sid
    online[ext] = sid
    print(f"✅ [CONNECTED] Ext {ext} (User: {user_id}) terhubung dengan SID {sid}. Total online: {len(online)}")


# ---------------------------------------------------------------------------
# 2. Handler Event Disconnect
# ---------------------------------------------------------------------------
@sio.event
async def disconnect(sid: str):
    session = await sio.get_session(sid)
    if session and "ext" in session:
        ext = session["ext"]

        # 1. Bersihkan status online jika SID yang disconnect adalah SID aktif
        if online.get(ext) == sid:
            del online[ext]
            print(f"🔌 [DISCONNECTED] Ext {ext} (SID {sid}) terputus. Total online: {len(online)}")
        else:
            print(f"🔌 [DISCONNECTED] SID {sid} lama telah terputus (sudah digantikan SID baru).")

        # 2. Jika extension memiliki panggilan aktif saat disconnect mendadak, akhiri panggilan
        active_call_id = extension_calls.get(ext)
        if active_call_id:
            print(f"⚠️ [ABRUPT DISCONNECT] Ext {ext} terputus saat panggilan {active_call_id} masih aktif. Menutup panggilan...")
            fake_pool.cancel_call(active_call_id)
            async with AsyncSessionLocal() as db:
                await CallManager.end(
                    db=db,
                    call_id=active_call_id,
                    reason="caller_disconnected",
                    ended_by="system",
                    sip_code=487,
                )
            cleanup_active_call(active_call_id, ext)
    else:
        print(f"🔌 [DISCONNECTED] SID {sid} terputus (tanpa sesi).")


# ---------------------------------------------------------------------------
# 3. Handler Event Call Make / Invite (Memulai Panggilan)
# ---------------------------------------------------------------------------
@sio.on("call:make")
@sio.on("call:invite")
@sio.on("call:start")
async def handle_call_make(sid: str, data: Any = None):
    """
    Handler untuk memulai panggilan:
    - Identitas penelpon diambil dari session server (bukan dari client payload).
    - Validasi nomor tujuan: hanya angka (to_number.isdigit()).
    - Batas 1 call per extension: tolak jika extension sudah punya panggilan aktif.
    - Catat status 'invited' di database via CallManager.
    - Jadwalkan simulasi ringing/answer/ended melalui FakePool.
    """
    # 1. Autentikasi Pengguna dari Session Server
    session = await get_authenticated_user(sid)
    if not session or "ext" not in session:
        await sio.emit("call:error", {
            "error": "Sesi tidak terautentikasi.",
            "code": "UNAUTHORIZED"
        }, to=sid)
        return

    from_ext = str(session["ext"])

    # 2. Ekstraksi Nomor Tujuan
    to_number = None
    if isinstance(data, dict):
        to_number = data.get("to") or data.get("to_number") or data.get("destination")
    elif isinstance(data, (str, int)):
        to_number = str(data)

    to_number = str(to_number).strip() if to_number is not None else ""

    # 3. Validasi Nomor Tujuan (HANYA ANGKA)
    if not to_number or not to_number.isdigit():
        await sio.emit("call:error", {
            "error": "Nomor tujuan tidak valid. Hanya angka yang diperbolehkan.",
            "code": "INVALID_NUMBER",
            "to": to_number,
        }, to=sid)
        return

    # 4. Batas 1 Call per Extension (Tolak jika extension sudah memiliki panggilan aktif)
    if from_ext in extension_calls:
        active_call_id = extension_calls[from_ext]
        await sio.emit("call:error", {
            "error": f"Extension {from_ext} sedang memiliki panggilan aktif ({active_call_id}).",
            "code": "CALL_ALREADY_ACTIVE",
            "active_call_id": active_call_id,
        }, to=sid)
        return

    # 5. Buat call_id unik dan simpan ke database (state: 'invited', jam server UTC)
    call_id = f"call_{uuid.uuid4().hex[:12]}"
    async with AsyncSessionLocal() as db:
        call_log = await CallManager.start(
            db=db,
            call_id=call_id,
            from_ext=from_ext,
            to_number=to_number,
            direction="outbound",
        )

    # 6. Catat ke in-memory tracking
    active_calls[call_id] = {
        "call_id": call_id,
        "from_ext": from_ext,
        "to_number": to_number,
        "sid": sid,
        "invited_at": call_log.invited_at,
    }
    extension_calls[from_ext] = call_id

    print(f"📞 [CALL INITIATED] Call {call_id} dari Ext {from_ext} ke {to_number}")

    # 7. Berikan respon awal ke client (call:invited)
    await sio.emit("call:invited", {
        "call_id": call_id,
        "from_ext": from_ext,
        "to": to_number,
        "to_number": to_number,
        "state": "invited",
    }, to=sid)

    # 8. Jadwalkan FakePool untuk membalas ringing, answer, dan ended
    await fake_pool.schedule_call(
        call_id=call_id,
        from_ext=from_ext,
        to_number=to_number,
        sid=sid,
        sio_server=sio,
        on_cleanup=cleanup_active_call,
    )


# ---------------------------------------------------------------------------
# 4. Handler Event Call Hangup (Mengakhiri Panggilan)
# ---------------------------------------------------------------------------
@sio.on("call:hangup")
@sio.on("call:end")
async def handle_call_hangup(sid: str, data: Any = None):
    """
    Handler untuk mengakhiri panggilan secara manual oleh user:
    - Hangup HANYA boleh dilakukan oleh pemilik panggilan (caller from_ext).
    - Batalkan task simulasi FakePool jika masih berjalan.
    - Catat status 'ended' dan billsec di database via CallManager.
    - Emit event 'call:ended' ke client.
    """
    # 1. Autentikasi Pengguna
    session = await get_authenticated_user(sid)
    if not session or "ext" not in session:
        await sio.emit("call:error", {
            "error": "Sesi tidak terautentikasi.",
            "code": "UNAUTHORIZED"
        }, to=sid)
        return

    from_ext = str(session["ext"])

    # 2. Ambil call_id dari payload atau dari tracking panggilan aktif milik extension
    call_id = None
    if isinstance(data, dict):
        call_id = data.get("call_id")
    elif isinstance(data, str):
        call_id = data.strip()

    if not call_id:
        call_id = extension_calls.get(from_ext)

    if not call_id:
        await sio.emit("call:error", {
            "error": "Tidak ada panggilan aktif yang ditemukan untuk di-hangup.",
            "code": "CALL_NOT_FOUND",
        }, to=sid)
        return

    # 3. Validasi Kepemilikan Panggilan (HANYA PEMILIK CALL YANG BOLEH HANGUP)
    call_info = active_calls.get(call_id)
    if call_info:
        if str(call_info.get("from_ext")) != from_ext:
            await sio.emit("call:error", {
                "call_id": call_id,
                "error": "Hangup ditolak: Anda bukan pemilik panggilan ini.",
                "code": "FORBIDDEN",
            }, to=sid)
            return
        to_number = call_info.get("to_number", "")
    else:
        # Jika sudah tidak ada di in-memory active_calls, cek kepemilikan di database
        async with AsyncSessionLocal() as db:
            call_log = await get_call_log_by_id(db, call_id)
            if not call_log:
                await sio.emit("call:error", {
                    "call_id": call_id,
                    "error": "Panggilan tidak ditemukan.",
                    "code": "CALL_NOT_FOUND",
                }, to=sid)
                return

            if str(call_log.from_ext) != from_ext:
                await sio.emit("call:error", {
                    "call_id": call_id,
                    "error": "Hangup ditolak: Anda bukan pemilik panggilan ini.",
                    "code": "FORBIDDEN",
                }, to=sid)
                return
            to_number = call_log.to_number

    # 4. Batalkan task terjadwal di FakePool jika belum selesai
    fake_pool.cancel_call(call_id)

    # 5. Akhiri panggilan di DB via CallManager (menghitung billsec presisi)
    async with AsyncSessionLocal() as db:
        ended_log = await CallManager.end(
            db=db,
            call_id=call_id,
            reason="caller_hangup",
            ended_by="caller",
            sip_code=200,
        )

    # 6. Bersihkan tracking memory
    cleanup_active_call(call_id, from_ext)

    billsec = ended_log.billsec if ended_log else 0
    print(f"📴 [CALL HANGUP] Call {call_id} di-hangup oleh caller {from_ext}. Billsec: {billsec}")

    # 7. Beritahu client bahwa panggilan telah berakhir
    await sio.emit("call:ended", {
        "call_id": call_id,
        "from_ext": from_ext,
        "to_number": to_number,
        "state": "ended",
        "billsec": billsec,
        "reason": "caller_hangup",
        "ended_by": "caller",
    }, to=sid)
