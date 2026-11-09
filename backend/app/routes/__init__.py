"""Domain routers. Agent A: cases, workers, diary, demo. Agent B: letters (+ employer, voice_profile in main.py)."""
from .cases import ROUTERS as CASE_ROUTERS
from .demo import router as demo_router
from .letters import router as letters_router

ROUTERS = [*CASE_ROUTERS, demo_router, letters_router]
