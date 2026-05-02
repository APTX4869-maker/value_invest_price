from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import init_db
from .routers import (
    companies_router,
    discovery_router,
    health_router,
    notes_router,
    research_queue_router,
    settings_router,
    valuation_router,
    watchlist_router,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="本地美股估值研究系统", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(watchlist_router)
app.include_router(companies_router)
app.include_router(discovery_router)
app.include_router(research_queue_router)
app.include_router(valuation_router)
app.include_router(notes_router)
app.include_router(settings_router)
