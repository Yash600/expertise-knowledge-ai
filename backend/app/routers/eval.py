"""
routers/eval.py — GET /eval/results, POST /eval/run

Exposes RAGAS evaluation results so the frontend admin panel can display them.
Running a full eval is expensive (15+ LLM calls) — results are cached to disk.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

from app.auth import get_current_user

router = APIRouter(prefix="/eval", tags=["evaluation"])

RESULTS_PATH = Path(__file__).parent.parent.parent / "results" / "ragas_results.json"


@router.get("/results")
async def get_eval_results(user: dict = Depends(get_current_user)):
    """
    Return the most recent evaluation results.
    Returns 404 if no evaluation has been run yet.
    """
    if not RESULTS_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail="No evaluation results found. Run: python -m app.eval.ragas_eval"
        )
    with open(RESULTS_PATH) as f:
        data = json.load(f)
    return JSONResponse(data)


@router.post("/run")
async def trigger_eval(
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
):
    """
    Trigger a lightweight evaluation run in the background (no RAGAS to avoid rate limits).
    Results will be available at GET /eval/results once complete.
    """
    def _run():
        import asyncio
        from app.eval.ragas_eval import evaluate
        asyncio.run(evaluate(
            output_path=str(RESULTS_PATH),
            use_ragas=False,   # offline — fast
        ))

    background_tasks.add_task(_run)
    return {"message": "Evaluation started in background. Check /eval/results in ~2 minutes."}
