from typing import Any

from fastapi import FastAPI

from app.routes.minutes import router as minutes_router
from app.routes.news import router as news_router
from app.routes.segments import router as segments_router


def register_routes(app: FastAPI, *, dependencies: list[Any] | None = None) -> None:
    dep = dependencies or []
    app.include_router(news_router, dependencies=dep)
    app.include_router(minutes_router, dependencies=dep)
    app.include_router(segments_router, dependencies=dep)
