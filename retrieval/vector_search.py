"""
retrieval/vector_search.py

Semantic search over the Qdrant collection built in Step 3 — used when
a question has no specific ticket ID to look up in the graph, but needs
similar past cases based on meaning (e.g. "how do we handle refund
complaints" — no ticket number, but a real precedent question).
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

import os
from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import QdrantVectorStore

load_dotenv()

COLLECTION_NAME = "support-ticket-text"


def load_vector_store():
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_kwargs={"device": "cpu"},
    )
    return QdrantVectorStore.from_existing_collection(
        embedding=embeddings,
        collection_name=COLLECTION_NAME,
        url=os.getenv("QDRANT_URL"),
        api_key=os.getenv("QDRANT_API_KEY"),
    )


def search_similar_tickets(query, k=5):
    """Returns matched documents with ticket_id + type metadata, so the
    caller can jump back into the graph for full context if needed."""
    store = load_vector_store()
    return store.similarity_search(query, k=k)