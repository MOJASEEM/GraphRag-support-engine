import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

import json
import random
import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
CSV_FILENAME = "customer_support_tickets.csv"
OUTPUT_FILE = Path(__file__).resolve().parent / "golden_dataset.json"
SAMPLE_SIZE = 20


def main():
    df = pd.read_csv(DATA_DIR / CSV_FILENAME).fillna("")

    # Only tickets that are actually closed AND have real resolution
    # text are usable as ground truth — same filtering logic as the
    # get_similar_resolved_tickets() query in graph/retriever.py.
    closed = df[(df["Ticket Status"] == "Closed") & (df["Resolution"].str.strip() != "")]

    print(f"Found {len(closed)} closed ticket(s) with resolution text.")

    if len(closed) < SAMPLE_SIZE:
        print(f"Only {len(closed)} available — using all of them.")
        sample = closed
    else:
        sample = closed.sample(n=SAMPLE_SIZE, random_state=7)

    golden_dataset = []
    for _, row in sample.iterrows():
        golden_dataset.append({
            "ticket_id": str(row["Ticket ID"]),
            "question": f"What's happening with ticket {row['Ticket ID']}?",
            "actual_resolution": row["Resolution"],
            "issue_type": row["Ticket Type"],
            "product": row["Product Purchased"],
        })

    with open(OUTPUT_FILE, "w") as f:
        json.dump(golden_dataset, f, indent=2)

    print(f"Saved {len(golden_dataset)} golden test case(s) to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()