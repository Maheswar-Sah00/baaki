"""Domain routers. Agent A: cases, workers, diary, demo. Agent B: letters (+ employer, voice_profile in main.py).
Tournament features (one agent owns each module): verify, check, proof, exit, inbox."""
from .cases import ROUTERS as CASE_ROUTERS
from .demo import router as demo_router
from .letters import router as letters_router
from .verify import router as verify_router
from .check import router as check_router
from .proof import router as proof_router
from .exit import router as exit_router
from .inbox import router as inbox_router
from .dues import router as dues_router  # add-on: Baaki for every promise (/api/dues)
from .raise_ import router as raise_router  # Haq Raise (/api/raise)

ROUTERS = [*CASE_ROUTERS, demo_router, letters_router,
           verify_router, check_router, proof_router, exit_router, inbox_router,
           dues_router,  # dues: add-on "Baaki for every promise"
           raise_router]  # Haq Raise
