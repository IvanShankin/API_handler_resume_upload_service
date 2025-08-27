from fastapi import APIRouter

from src.requests.post import router as post_router
from src.requests.delete import router as delete_router

main_router = APIRouter()

main_router.include_router(post_router)
main_router.include_router(delete_router)

__all__ = ['main_router']