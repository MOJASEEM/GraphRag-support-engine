"""
ingestion/load_vectors.py

Loads ticket Description + Resolution text into Qdrant, tagged by type
so the retriever can distinguish "what went wrong" from "how it was
solved" when searching.

Run with:  python ingestion/load_vectors.py
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

import os
import pandas as pd
from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

load_dotenv()

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
CSV_FILENAME = "customer_support_tickets.csv"
COLLECTION_NAME = "support-ticket-text"


def load_csv():
    df = pd.read_csv(DATA_DIR / CSV_FILENAME)
    df = df.fillna("")
    return df


def build_documents(df):
    documents = []
    for _, row in df.iterrows():
        ticket_id = row["Ticket ID"]

        if str(row["Ticket Description"]).strip():
            documents.append(Document(
                page_content=row["Ticket Description"],
                metadata={"ticket_id": ticket_id, "type": "description"},
            ))

        if str(row["Resolution"]).strip():
            documents.append(Document(
                page_content=row["Resolution"],
                metadata={"ticket_id": ticket_id, "type": "resolution"},
            ))

    print(f"   {len(documents)} document(s) built (description + resolution text).")
    return documents


def ensure_collection_exists(client, dimension=384):
    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME not in existing:
        print(f"Creating Qdrant collection '{COLLECTION_NAME}'...")
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=dimension, distance=Distance.COSINE),
        )
    else:
        print(f"Collection '{COLLECTION_NAME}' already exists, reusing it.")


def main():
    df = load_csv()
    documents = build_documents(df)

    client = QdrantClient(
        url=os.getenv("QDRANT_URL"),
        api_key=os.getenv("QDRANT_API_KEY"),
    )
    ensure_collection_exists(client)

    print("Creating embeddings and uploading to Qdrant...")
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_kwargs={"device": "cpu"},
    )

    QdrantVectorStore.from_documents(
        documents=documents,
        embedding=embeddings,
        url=os.getenv("QDRANT_URL"),
        api_key=os.getenv("QDRANT_API_KEY"),
        collection_name=COLLECTION_NAME,
    )

    print(f"\n✅ Uploaded {len(documents)} document(s) to Qdrant collection '{COLLECTION_NAME}'.")


if __name__ == "__main__":
    main()