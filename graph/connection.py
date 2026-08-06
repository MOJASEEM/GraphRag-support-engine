"""
Neo4j connection handler — shared by ingestion and retrieval code.

Why this exists as its own module: every later step (loading data,
querying the graph) needs a driver connection. Centralizing it here
means we configure it once and avoid the same "heavy work runs on
import" mistake we hit in the HR project's ingest.py — this module
only CONNECTS when you explicitly call get_driver(), never on import.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")


def _candidate_uris(uri: str) -> list[str]:
    """Build a small list of candidate URIs to try in order."""
    if not uri:
        return []

    candidates = [uri.strip()]
    normalized = candidates[0]

    if normalized.startswith("neo4j+s://"):
        candidates.append(normalized.replace("neo4j+s://", "neo4j://", 1))
        candidates.append(normalized.replace("neo4j+s://", "bolt://", 1))
    elif normalized.startswith("neo4j://"):
        candidates.append(normalized.replace("neo4j://", "bolt://", 1))
    elif normalized.startswith("bolt://"):
        candidates.append(normalized.replace("bolt://", "neo4j://", 1))

    candidates.extend(["neo4j://localhost:7687", "bolt://localhost:7687"])

    unique_candidates: list[str] = []
    seen = set()
    for candidate in candidates:
        if candidate and candidate not in seen:
            unique_candidates.append(candidate)
            seen.add(candidate)
    return unique_candidates


def get_driver():
    """Create a Neo4j driver instance. Caller is responsible for closing it."""
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")

    if not all([uri, user, password]):
        raise ValueError(
            "Missing Neo4j credentials. Check that NEO4J_URI, NEO4J_USER, "
            "and NEO4J_PASSWORD are set in your .env file."
        )

    last_error = None
    for candidate_uri in _candidate_uris(uri):
        driver = None
        try:
            driver = GraphDatabase.driver(
                candidate_uri,
                auth=(user, password),
                connection_timeout=5,
            )
            with driver.session() as session:
                session.run("RETURN 1 AS ok").single()
            return driver
        except Exception as exc:
            last_error = exc
            if driver is not None:
                driver.close()

    raise RuntimeError(
        "Could not connect to Neo4j. Check that the configured URI is reachable "
        "and that NEO4J_URI, NEO4J_USER, and NEO4J_PASSWORD are correct. "
        f"Last error: {last_error}"
    ) from last_error


def verify_connection():
    """Quick sanity check — run this first before writing any ingestion code."""
    driver = None
    try:
        driver = get_driver()
        print("✅ Connected to Neo4j successfully.")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
    finally:
        if driver is not None:
            driver.close()


if __name__ == "__main__":
    verify_connection()