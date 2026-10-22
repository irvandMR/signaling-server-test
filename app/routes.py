from fastapi import APIRouter
from controller.health_controller import router as health_router
from controller.auth_controller import router as auth_router
from sockets.health_socket import router as socket_router  

api_router = APIRouter()

# Register Routers
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(socket_router)
