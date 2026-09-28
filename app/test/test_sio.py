import socketio
import asyncio

async def main():
    sio = socketio.AsyncClient()
    
    @sio.on('connect')
    def on_connect():
        print("✅ Terhubung ke server!")
        
    @sio.on('connected')
    def on_message(data):
        print(f"📩 Pesan dari server: {data}")

    try:
        # Kirim koneksi dengan auth (menggunakan kunci user_id)
        await sio.connect('http://127.0.0.1:8081', auth={'user': '115011', 'password': 'Pass1234'})
        print("SID Saya:", sio.sid)
        
        # Biarkan menyala selama 5 detik untuk menerima pesan
        await asyncio.sleep(5)
        
        await sio.disconnect()
    except Exception as e:
        print("❌ Error:", e)

if __name__ == "__main__":
    asyncio.run(main())
