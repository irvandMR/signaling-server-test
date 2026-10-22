from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from repository.users_account_repository import get_all_users

router = APIRouter(tags=["Health Check"])

@router.get("/health")
async def health_check():
    return {
        "status": "running .....",
        "service": "Websocket Signaling Service"
    }

# Endpoint uji database:
@router.get("/health/db")
async def test_db(db: AsyncSession = Depends(get_db)):
    users = await get_all_users(db)
    return {
        "status": "database connected",
        "total": len(users),
        "data": [
            {
                "account_id": u.account_id,
                "account_name": u.account_name,
                "account_extension": u.account_extension,
                "sip_ha1" : u.sip_ha1   
            }
            for u in users
        ]
    }
