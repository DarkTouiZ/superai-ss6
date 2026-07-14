"""SuperAI SS6 — autonomous AI software-engineering pipeline.

Public API (import these directly):

    from agent_pipeline import retrieve, plan, debate, execute, run, score_plan

CLI (installed as a console script):

    ss6 rag "how is a delivery fee computed?"
    ss6 plan "Add a top-customers-by-spend screen"
    ss6 run  "Add ALL Member points redemption" --out ./out
    ss6 plan --intake examples/top_customers_intake.json
    ss6 approve --plan B --approved-by "Safe"
"""
__version__ = "1.2.0"

from agent_pipeline.api import (  # noqa: F401,E402
    retrieve,
    plan,
    debate,
    execute,
    run,
    score_plan,
    approve,
)

__all__ = ["retrieve", "plan", "debate", "execute", "run", "score_plan", "approve", "__version__"]
