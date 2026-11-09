"""Domain routers. Placeholders for now: every endpoint answers 501 until it is built."""
from .cases import router as cases_router
from .letters import router as letters_router

ROUTERS = [cases_router, letters_router]
