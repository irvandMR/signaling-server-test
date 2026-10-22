from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from core.config import configs

# 1. Buat Engine Async
# pool_pre_ping=True: memastikan koneksi database masih hidup sebelum dipakai
# echo=False: ubah ke True jika ingin melihat raw SQL log di terminal
engine = create_async_engine(
    configs.DATABASE,
    echo=False,
    future=True,
    pool_pre_ping=True,
)

# 2. Factory SessionLocal untuk AsyncSession
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

# Alias agar familiar dengan konvensi SessionLocal
SessionLocal = AsyncSessionLocal


# 3. Base Class untuk Model SQLAlchemy
class Base(DeclarativeBase):
    pass


# 4. Dependency Injection untuk FastAPI Controller
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
