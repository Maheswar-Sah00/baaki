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
# Tournament ranks 6-10 (one agent owns each module).
from .consent import router as consent_router  # G13 spoken consent = voice sample (/api/consent)
from .sandbox import router as sandbox_router  # V04 Be Sharma ji sandbox (/api/sandbox)
from .quiz import router as quiz_router  # V08 Fair or Not? (/api/quiz)
from .story import router as story_router  # V12 Case Replay (/api/story)
from .hisaab import router as hisaab_router  # V09 Hisaab Milao (/api/hisaab)

ROUTERS = [*CASE_ROUTERS, demo_router, letters_router,
           verify_router, check_router, proof_router, exit_router, inbox_router,
           dues_router,  # dues: add-on "Baaki for every promise"
           raise_router,  # Haq Raise
           consent_router, sandbox_router, quiz_router, story_router, hisaab_router]  # ranks 6-10
