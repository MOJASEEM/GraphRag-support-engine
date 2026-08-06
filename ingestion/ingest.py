from pathlib import Path

from datasets import load_dataset

csv_path = Path(__file__).resolve().parents[1] / "data" / "customer_support_tickets.csv"

if not csv_path.exists():
    raise FileNotFoundError(f"CSV file not found: {csv_path}")

# Load directly via Hugging Face
dataset = load_dataset("csv", data_files=str(csv_path), split="train")
print(dataset[0])