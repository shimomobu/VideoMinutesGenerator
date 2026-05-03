"""FastAPI アプリケーション"""
from __future__ import annotations

from fastapi import FastAPI

from .routes import router


def create_app() -> FastAPI:
    app = FastAPI(
        title="VideoMinutesGenerator API",
        version="0.1.0",
        description="会議動画から議事録を自動生成する REST API",
    )
    app.include_router(router)
    return app


app = create_app()
