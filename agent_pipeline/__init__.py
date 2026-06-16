"""SuperAI SS6 — autonomous AI software-engineering pipeline.

Public API (import these directly):

    from agent_pipeline import retrieve, plan, debate, execute, run, score_plan

CLI (installed as a console script):

    ss6 rag "how is a delivery fee computed?"
    ss6 plan "Add a top-customers-by-spend screen"
    ss6 run  "Add ALL Member points redemption" --out ./out
"""
__version__ = "1.0.0"

from agent_pipeline.api import (  # noqa: F401,E402
    retrieve,
    plan,
    debate,
    execute,
    run,
    score_plan,
)

__all__ = ["retrieve", "plan", "debate", "execute", "run", "score_plan", "__version__"]
