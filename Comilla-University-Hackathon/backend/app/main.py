"""The FastAPI app. Run from backend/:  uvicorn app.main:app --reload --port 8000"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings, get_settings
from app.container import Container
from app.interfaces.api.errors import register_error_handlers
from app.interfaces.api.routers import admin, callback, chat, clusters, health, history, services, tts
from app.interfaces.voice import router as voice

log = logging.getLogger("ekcall")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        for warning in settings.config_warnings():
            log.warning("config: %s", warning)
        container = Container(settings)
        try:
            container.init_database()
        except Exception:  # keep running: /health will show db=error
            log.exception("could not create database tables")
        container.warm_up()  # models load in the background (PRELOAD_MODELS), D2-T4
        app.state.container = container
        log.info(
            "Ek Call started (env=%s, llm=%s, router=%s, sms=%s)",
            settings.app_env,
            settings.llm_backend,
            settings.router_backend,
            settings.sms_backend,
        )
        yield
        container.close()

    app = FastAPI(
        title="Ek Call API",
        version="0.1.0",
        description="Bangla voice AI agent for government services.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.frontend_origin_list,  # only our frontend (NFR-SEC-02)
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(app)
    # Every router is registered here once. Add routes inside your own router file; this list
    # should not need changes (docs/BUILD_PLAN.md Section 0.4).
    app.include_router(health.router)
    app.include_router(services.router)
    app.include_router(chat.router)
    app.include_router(history.router)
    app.include_router(voice.router)  # D1-A3, D1-A5, D2-A1, D2-A2
    app.include_router(callback.router)  # D2-A1
    app.include_router(tts.router)  # D2-R2
    app.include_router(admin.router)  # D2-R1
    app.include_router(clusters.router)  # D2-T2
    return app


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
app = create_app()
