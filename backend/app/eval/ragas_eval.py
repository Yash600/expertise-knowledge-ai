"""
eval/ragas_eval.py — RAGAS-based evaluation of the RAG pipeline.

Metrics measured:
  faithfulness        — Is the answer grounded in the retrieved context? (0-1)
  answer_relevance    — Does the answer address the question? (0-1)
  context_precision   — Are retrieved chunks actually relevant? (0-1)
  context_recall      — Do retrieved chunks cover the ground truth? (0-1)

Also measures:
  query_type_accuracy — Did the classifier route correctly?
  out_of_scope_refusal_rate — Did it refuse OOS questions?
  hallucination_cases — List of cases where answer went beyond context

Usage:
  python -m app.eval.ragas_eval --output results/ragas_results.json

Requires:
  pip install ragas datasets
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")

# Add backend root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


async def run_pipeline_for_eval(question: str, session_id: str) -> Dict[str, Any]:
    """Run the RAG pipeline and return full state for evaluation."""
    from app.graph.pipeline import run_pipeline
    result = await run_pipeline(
        query=question,
        session_id=session_id,
        user_id="eval_user",
    )
    return result


def _check_refuses_oos(answer: str) -> bool:
    """Check if the answer correctly refuses an out-of-scope question."""
    refusal_phrases = [
        "only answer questions based on",
        "outside my scope",
        "can only help with",
        "not in my knowledge base",
        "cannot help with",
        "outside the scope",
        "only assist with",
    ]
    answer_lower = answer.lower()
    return any(phrase in answer_lower for phrase in refusal_phrases)


def _check_hallucinates(answer: str, context_texts: List[str]) -> bool:
    """
    Simple hallucination heuristic: check if answer contains specific claims
    not present in any retrieved context chunk.

    This is a lightweight check — RAGAS faithfulness is the proper metric.
    """
    # If no context was retrieved but answer gives specific facts, flag it
    if not context_texts and len(answer) > 100:
        generic_phrases = [
            "i cannot", "i don't", "not available", "not mentioned",
            "no information", "uploaded documents", "knowledge base"
        ]
        answer_lower = answer.lower()
        if not any(p in answer_lower for p in generic_phrases):
            return True  # Specific answer with no context = possible hallucination
    return False


async def evaluate(
    output_path: str = "results/ragas_results.json",
    use_ragas: bool = True,
    delay_between_cases: float = 4.0,
) -> Dict[str, Any]:
    """
    Run all test cases through the pipeline and compute metrics.

    Args:
        output_path: Where to save the JSON results.
        use_ragas: Whether to run RAGAS (requires API key + internet).
                   Set False for offline lightweight evaluation.
        delay_between_cases: Seconds to sleep between cases (avoids RPM limits).

    Returns:
        Evaluation results dict.
    """
    from app.eval.test_dataset import TEST_CASES

    print(f"\n{'='*60}")
    print("Enterprise Knowledge Assistant — RAG Evaluation")
    print(f"{'='*60}")
    print(f"Running {len(TEST_CASES)} test cases...\n")

    results = []
    category_scores: Dict[str, List[float]] = {}

    # For RAGAS
    ragas_questions = []
    ragas_answers = []
    ragas_contexts = []
    ragas_ground_truths = []

    for i, case in enumerate(TEST_CASES):
        if i > 0:
            await asyncio.sleep(delay_between_cases)
        session_id = f"eval-{i}-{int(time.time())}"
        print(f"[{i+1:02d}/{len(TEST_CASES)}] {case['category'].upper()} | {case['question'][:60]}...")

        t0 = time.time()
        try:
            result = await run_pipeline_for_eval(case["question"], session_id)
            latency_ms = int((time.time() - t0) * 1000)

            answer = result.get("answer", "")
            query_type = result.get("query_type", "UNKNOWN")
            chunks = result.get("retrieved_chunks", [])
            context_texts = [c.get("text", "") for c in chunks]
            confidence = result.get("confidence", 0.0)

            # ── Per-case evaluation ───────────────────────────────────────────
            # 1. Query type correctness
            expected_types = {
                "accuracy": ["DOCUMENT_QUERY", "OVERVIEW", "FULL_SCAN"],
                "relevance": ["DOCUMENT_QUERY", "OVERVIEW", "FULL_SCAN"],
                "hallucination": ["DOCUMENT_QUERY"],
                "out_of_scope": ["OUT_OF_SCOPE"],
                "conversational": ["CONVERSATIONAL"],
                "ambiguity": ["AMBIGUOUS"],
            }
            expected = expected_types.get(case["category"], ["DOCUMENT_QUERY"])
            type_correct = query_type in expected

            # 2. OOS refusal
            oos_correct = None
            if case["category"] == "out_of_scope":
                oos_correct = _check_refuses_oos(answer)

            # 3. Hallucination flag
            hallucination_flag = _check_hallucinates(answer, context_texts)

            # 4. Has sources
            has_sources = len(chunks) > 0 and case["category"] not in ("out_of_scope", "conversational", "ambiguity")

            case_result = {
                "question": case["question"],
                "category": case["category"],
                "difficulty": case["difficulty"],
                "expected_behavior": case["expected_behavior"],
                "answer": answer,
                "query_type": query_type,
                "query_type_correct": type_correct,
                "oos_refusal_correct": oos_correct,
                "hallucination_flagged": hallucination_flag,
                "confidence": confidence,
                "chunks_retrieved": len(chunks),
                "latency_ms": latency_ms,
                "ground_truth": case["ground_truth"],
            }
            results.append(case_result)

            # For RAGAS dataset
            if context_texts and case["category"] not in ("out_of_scope", "conversational"):
                ragas_questions.append(case["question"])
                ragas_answers.append(answer)
                ragas_contexts.append(context_texts[:3])  # top 3 contexts
                ragas_ground_truths.append(case["ground_truth"])

            status = "✅" if (type_correct and not hallucination_flag) else "⚠️"
            print(f"       {status} type={query_type} | chunks={len(chunks)} | {latency_ms}ms")

        except Exception as e:
            err_str = str(e)
            is_tpd = "tokens per day" in err_str.lower() or "tpd" in err_str.lower()
            label = "TPD_LIMIT" if is_tpd else "ERROR"
            if is_tpd:
                print(f"       ⛔ Daily token limit hit — stopping eval early.")
                # Save partial results so the run isn't completely lost
                results.append({
                    "question": case["question"],
                    "category": case["category"],
                    "difficulty": case["difficulty"],
                    "error": "Daily token limit (TPD) exceeded — partial results saved",
                    "query_type": label,
                    "query_type_correct": False,
                })
                break  # No point continuing — all remaining cases will also fail
            print(f"       ❌ ERROR: {e}")
            results.append({
                "question": case["question"],
                "category": case["category"],
                "difficulty": case["difficulty"],
                "error": err_str,
                "query_type": label,
                "query_type_correct": False,
            })

    # ── Aggregate metrics ─────────────────────────────────────────────────────
    total = len(results)
    successful = [r for r in results if "error" not in r]

    type_accuracy = sum(1 for r in successful if r.get("query_type_correct")) / max(len(successful), 1)

    oos_cases = [r for r in successful if r.get("oos_refusal_correct") is not None]
    oos_accuracy = sum(1 for r in oos_cases if r.get("oos_refusal_correct")) / max(len(oos_cases), 1)

    hallucination_cases = [r for r in successful if r.get("hallucination_flagged")]
    avg_confidence = sum(r.get("confidence", 0) for r in successful) / max(len(successful), 1)
    avg_latency = sum(r.get("latency_ms", 0) for r in successful) / max(len(successful), 1)

    # ── RAGAS metrics (if available) ─────────────────────────────────────────
    ragas_scores = {}
    if use_ragas and ragas_questions:
        try:
            print(f"\nRunning RAGAS on {len(ragas_questions)} document-query cases...")
            from datasets import Dataset
            from ragas import evaluate as ragas_evaluate
            from ragas.metrics import (
                faithfulness,
                answer_relevancy,
                context_precision,
                context_recall,
            )
            from langchain_groq import ChatGroq
            from langchain_openai import OpenAIEmbeddings

            # RAGAS needs an LLM and embedder
            ragas_llm = ChatGroq(
                model="llama-3.3-70b-versatile",
                api_key=os.getenv("GROQ_API_KEY"),
                temperature=0,
            )

            ragas_dataset = Dataset.from_dict({
                "question": ragas_questions,
                "answer": ragas_answers,
                "contexts": ragas_contexts,
                "ground_truth": ragas_ground_truths,
            })

            ragas_result = ragas_evaluate(
                ragas_dataset,
                metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
                llm=ragas_llm,
            )
            ragas_scores = {
                "faithfulness": round(float(ragas_result["faithfulness"]), 4),
                "answer_relevancy": round(float(ragas_result["answer_relevancy"]), 4),
                "context_precision": round(float(ragas_result["context_precision"]), 4),
                "context_recall": round(float(ragas_result["context_recall"]), 4),
            }
            print(f"  RAGAS scores: {ragas_scores}")
        except Exception as e:
            print(f"  RAGAS failed (non-fatal): {e}")
            ragas_scores = {"error": str(e)}

    # ── Build final report ────────────────────────────────────────────────────
    report = {
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "total_cases": total,
        "successful_cases": len(successful),
        "summary": {
            "query_type_accuracy": round(type_accuracy, 4),
            "out_of_scope_refusal_accuracy": round(oos_accuracy, 4),
            "hallucination_flags": len(hallucination_cases),
            "avg_confidence": round(avg_confidence, 4),
            "avg_latency_ms": round(avg_latency, 1),
        },
        "ragas_metrics": ragas_scores,
        "per_category": {},
        "test_cases": results,
        "hallucination_cases": [r["question"] for r in hallucination_cases],
    }

    # Per-category breakdown
    categories = set(r.get("category", "unknown") for r in successful)
    for cat in categories:
        cat_results = [r for r in successful if r.get("category") == cat]
        report["per_category"][cat] = {
            "count": len(cat_results),
            "type_accuracy": round(
                sum(1 for r in cat_results if r.get("query_type_correct")) / max(len(cat_results), 1), 4
            ),
            "avg_confidence": round(
                sum(r.get("confidence", 0) for r in cat_results) / max(len(cat_results), 1), 4
            ),
        }

    # Save results
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w") as f:
        json.dump(report, f, indent=2, default=str)

    # ── Print summary ─────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("EVALUATION SUMMARY")
    print(f"{'='*60}")
    print(f"  Cases run:               {total}")
    print(f"  Query type accuracy:     {type_accuracy:.1%}")
    print(f"  OOS refusal accuracy:    {oos_accuracy:.1%}")
    print(f"  Hallucination flags:     {len(hallucination_cases)}")
    print(f"  Avg confidence:          {avg_confidence:.1%}")
    print(f"  Avg latency:             {avg_latency:.0f}ms")
    if ragas_scores and "error" not in ragas_scores:
        print(f"\n  RAGAS Faithfulness:      {ragas_scores.get('faithfulness', 'N/A')}")
        print(f"  RAGAS Answer Relevancy:  {ragas_scores.get('answer_relevancy', 'N/A')}")
        print(f"  RAGAS Context Precision: {ragas_scores.get('context_precision', 'N/A')}")
        print(f"  RAGAS Context Recall:    {ragas_scores.get('context_recall', 'N/A')}")
    print(f"\n  Results saved to: {output}")
    print(f"{'='*60}\n")

    return report


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="results/ragas_results.json")
    parser.add_argument("--no-ragas", action="store_true", help="Skip RAGAS (faster, offline)")
    args = parser.parse_args()

    asyncio.run(evaluate(output_path=args.output, use_ragas=not args.no_ragas))
