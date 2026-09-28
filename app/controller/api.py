import fastapi
from app.socket.sockets import connected
from app.core.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.controller.user_controller import user_router

fastapi_app = fastapi.FastAPI(
    title="Signaling Service", 
    description="Signaling Service for WebRTC", 
    version="1.0.0"
)

# Daftarkan router user
fastapi_app.include_router(user_router)

@fastapi_app.get("/health")
async def health(db: AsyncSession = fastapi.Depends(get_db)):
    db_status = "terhubung"
    try:
        # Menjalankan query paling ringan untuk mengetes koneksi
        await db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"gagal terhubung ({str(e)})"
        
    return {
        "message": "Signaling Service is running",
        "database_status": db_status
    }
