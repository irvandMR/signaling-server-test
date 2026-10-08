import socketio
import asyncio

# Buat instance client socketio
sio = socketio.AsyncClient()

# Kredensial untuk testing (Sesuaikan dengan data user yang ada di database)
EXTENSION = "11099" # Ganti dengan ekstensi yang valid
PASSWORD = "Pass1234" # Ganti dengan password yang valid
PBX_IP = "127.0.0.1"

@sio.event
async def connect():
    print(f"[Client] Berhasil terkoneksi ke server dengan SID: {sio.sid}")

@sio.event
async def connect_error(data):
    print(f"[Client] Gagal terkoneksi: {data}")

@sio.event
async def disconnect():
    print("[Client] Terputus dari server.")

@sio.on("connected")
async def on_connected(data):
    print(f"[Client] Menerima event 'connected': {data}")
    # Simpan token jika ingin menggunakannya untuk event WebRTC nanti
    token = data.get("new_token")
    print(f"[Client] Token didapatkan: {token}")
    
    # --- TEST UDP MENTAH KE ASTERISK ---
    print("\n[Client] =========================================")
    print(f"[Client] Mengirim UDP Test Ping ke Asterisk di {PBX_IP}:5060...")
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(2)
        # Kirim pesan ngawur (Asterisk akan merespons dengan error jika menerimanya)
        sock.sendto(b"OPTIONS sip:1008@127.0.0.1 SIP/2.0\r\n\r\n", (PBX_IP, 5060))
        print("[Client] UDP Test Ping terkirim! Silakan cek log Asterisk Anda.")
    except Exception as e:
        print(f"[Client] Gagal mengirim UDP Test Ping: {e}")
        
    # --- MULAI SIMULASI PANGGILAN WEBRTC ---
    print("\n[Client] =========================================")
    print(f"[Client] Mencoba melakukan panggilan ke 1008...")
    
    # Mock SDP (Session Description Protocol) sederhana untuk testing
    mock_sdp = "v=0\r\no=- 123456 123456 IN IP4 127.0.0.1\r\ns=-\r\nc=IN IP4 127.0.0.1\r\nt=0 0\r\nm=audio 10000 RTP/SAVPF 111\r\n"
    
    await sio.emit("webrtc_offer", {
        "target": "1008",
        "token": token,
        "sdp": mock_sdp
    })
    print("[Client] =========================================\n")

@sio.on("webrtc_answer")
async def on_webrtc_answer(data):
    print(f"[Client] BERHASIL! Menerima jawaban WebRTC (SDP Answer) dari server:")
    print(data.get("sdp"))

@sio.on("webrtc_status")
async def on_webrtc_status(data):
    print(f"[Client] STATUS/ERROR WEBRTC: {data}")

async def main():
    try:
        print("[Client] Mencoba connect ke server...")
        
        # Kirim kredensial melalui param 'auth' (sesuai logic di sockets.py)
        await sio.connect(
            "http://localhost:8081",
            auth={"user": EXTENSION, "password": PASSWORD},
            transports=["websocket", "polling"]
        )
        
        # Tunggu beberapa detik untuk melihat balasan dari server (WebRTC test memakan waktu lebih lama untuk memproses)
        await asyncio.sleep(10)
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if sio.connected:
            await sio.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
