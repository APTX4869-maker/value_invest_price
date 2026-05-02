from .companies import router as companies_router
from .discovery import router as discovery_router
from .health import router as health_router
from .notes import router as notes_router
from .research_queue import router as research_queue_router
from .settings import router as settings_router
from .valuation import router as valuation_router
from .watchlist import router as watchlist_router

__all__ = [
    "companies_router",
    "discovery_router",
    "health_router",
    "notes_router",
    "research_queue_router",
    "settings_router",
    "valuation_router",
    "watchlist_router",
]
