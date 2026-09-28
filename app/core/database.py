from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from app.core.config import Settings
import functools

# Ambil URL Database dari config
DATABASE_URL = Settings.DATABASE_URL

# Buat engine (async)
engine = create_async_engine(DATABASE_URL, echo=True)

# Buat pembuat session
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Kelas dasar untuk model tabel-tabel di database
Base = declarative_base()

# Dependency injeksi untuk mengambil koneksi session ke database (digunakan di FastAPI)
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
