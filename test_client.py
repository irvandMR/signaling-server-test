import socketio
import asyncio

# Buat instance client socketio
sio = socketio.AsyncClient()

# Kredensial untuk testing (Sesuaikan dengan data user yang ada di database)
EXTENSION = "1001" # Ganti dengan ekstensi yang valid
PASSWORD = "password123" # Ganti dengan password yang valid

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

async def main():
    try:
        print("[Client] Mencoba connect ke server...")
        
        # Kirim kredensial melalui param 'auth' (sesuai logic di sockets.py)
        await sio.connect(
            "http://localhost:8081",
            auth={"user": EXTENSION, "password": PASSWORD},
            transports=["websocket", "polling"]
        )
        
        # Tunggu beberapa detik untuk melihat balasan dari server
        await asyncio.sleep(5)
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if sio.connected:
            await sio.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
