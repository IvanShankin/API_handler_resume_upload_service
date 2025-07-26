from fastapi import APIRouter

from srt.requests.get import router as get_router
from srt.requests.post import router as post_router

main_router = APIRouter()

main_router.include_router(get_router)
main_router.include_router(post_router)

__all__ = ['main_router']