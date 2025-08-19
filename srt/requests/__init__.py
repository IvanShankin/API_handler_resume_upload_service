from fastapi import APIRouter

from srt.requests.post import router as post_router
from srt.requests.delete import router as delete_router

main_router = APIRouter()

main_router.include_router(post_router)
main_router.include_router(delete_router)

__all__ = ['main_router']