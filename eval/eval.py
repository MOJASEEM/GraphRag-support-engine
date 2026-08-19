
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

import json
from graph.connection import get_driver
from graph.retriever import assemble_full_state
from retrieval.generate import get_llm, generate_resolution

GOLDEN_DATASET_FILE = Path(__file__).resolve().parent / "golden_dataset.json"


def load_golden_dataset():
    if not GOLDEN_DATASET_FILE.exists():
        raise FileNotFoundError("Run eval/build_golden_dataset.py first.")
    with open(GOLDEN_DATASET_FILE) as f:
        return json.load(f)


def check_faithfulness(answer, graph_state, llm):
    """checks if the
    answer grounded in the retrieved graph state, or did it invent
    details not present in the context?"""
    context = json.dumps(graph_state, indent=2, default=str)
    prompt = f"""You are a strict fact-checker. Compare the ANSWER to the
GRAPH DATA it was supposed to be based on.

GRAPH DATA:
{context}

ANSWER:
{answer}

Does the answer contain ONLY information supported by the graph data?
Reply with exactly one word: GROUNDED or HALLUCINATED."""
    response = llm.invoke(prompt)
    return response.content.strip().upper().startswith("GROUNDED")


def check_resolution_alignment(generated_answer, actual_resolution, llm):
    """LLM-as-judge, but critically: comparing against a REAL historical
    resolution, not an invented one. This is stronger ground truth than
    the HR project had."""
    prompt = f"""Compare the GENERATED RESOLUTION to the ACTUAL RESOLUTION
that was really used for this ticket. Judge if they suggest the same
core fix/action, even if worded differently.

ACTUAL RESOLUTION (real, historical):
{actual_resolution}

GENERATED RESOLUTION:
{generated_answer}

Reply with exactly one word: ALIGNED or MISALIGNED."""
    response = llm.invoke(prompt)
    return response.content.strip().upper().startswith("ALIGNED")


def run_evaluation():
    golden_dataset = load_golden_dataset()
    driver = get_driver()
    llm = get_llm()

    results = []

    try:
        print(f"Running evaluation on {len(golden_dataset)} test case(s)...\n")

        for i, item in enumerate(golden_dataset, 1):
            ticket_id = item["ticket_id"]
            print(f"[{i}/{len(golden_dataset)}] Ticket {ticket_id}")

            # 1. Retrieval — did the graph traversal find the ticket?
            graph_state = assemble_full_state(driver, ticket_id)
            retrieval_hit = graph_state is not None
            print(f"   Retrieval hit: {retrieval_hit}")

            if not retrieval_hit:
                results.append({"ticket_id": ticket_id, "retrieval_hit": False,
                                 "faithful": False, "aligned": False})
                continue

            # 2. Generation
            answer, _ = generate_resolution(graph_state, llm)

            # 3. Faithfulness
            faithful = check_faithfulness(answer, graph_state, llm)
            print(f"   Faithful: {faithful}")

            # 4. Resolution alignment vs REAL historical resolution
            aligned = check_resolution_alignment(answer, item["actual_resolution"], llm)
            print(f"   Aligned with actual resolution: {aligned}\n")

            results.append({
                "ticket_id": ticket_id,
                "retrieval_hit": retrieval_hit,
                "faithful": faithful,
                "aligned": aligned,
            })

    finally:
        driver.close()

    n = len(results)
    retrieval_rate = sum(r["retrieval_hit"] for r in results) / n * 100
    faithfulness_rate = sum(r["faithful"] for r in results) / n * 100
    alignment_rate = sum(r["aligned"] for r in results) / n * 100

    print("=" * 50)
    print("EVALUATION SUMMARY")
    print("=" * 50)
    print(f"Retrieval Hit Rate:           {retrieval_rate:.1f}%")
    print(f"Generation Faithfulness:      {faithfulness_rate:.1f}%")
    print(f"Resolution Alignment (real):  {alignment_rate:.1f}%")
    print("=" * 50)

    return results


if __name__ == "__main__":
    run_evaluation()