import functools
from app.core.database import AsyncSessionLocal

def with_db(func):
    """Decorator sebagai penjembatan database khusus untuk Socket.IO"""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        async with AsyncSessionLocal() as db:
            try:
                # Sisipkan db sebagai argumen pertama ke fungsi aslinya
                return await func(db, *args, **kwargs)
            finally:
                await db.close()
    return wrapper
