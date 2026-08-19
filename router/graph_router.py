"""
router/graph_router.py

LangGraph state machine for the support escalation engine. Classifies
each question, then routes to graph-based lookup, vector-based semantic
search, or a direct reply — mirroring the HR project's router pattern,
but deciding between graph traversal and vector search instead of
vectorstore vs. web search.

Run with:  python router/graph_router.py
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

import re
from typing import TypedDict, Optional, List
from langgraph.graph import StateGraph, END

from graph.connection import get_driver
from graph.retriever import assemble_full_state
from retrieval.generate import get_llm, generate_resolution
from retrieval.vector_search import search_similar_tickets


class RouterState(TypedDict):
    question: str
    route: Optional[str]
    ticket_id: Optional[str]
    graph_state: Optional[dict]
    search_results: Optional[List]
    answer: Optional[str]


ROUTER_PROMPT = """Classify the user's question into exactly ONE category:

- TICKET_LOOKUP: the question references a specific ticket by ID number.
- SEMANTIC_SEARCH: a general question about how issues are typically
  handled/resolved, with no specific ticket ID mentioned.
- DIRECT: a greeting or small talk, no lookup needed.

Question: {question}

Reply with exactly one word: TICKET_LOOKUP, SEMANTIC_SEARCH, or DIRECT."""


def extract_ticket_id(question):
    """Simple regex first (fast, free) — falls back to None if no
    number found, which the router treats as SEMANTIC_SEARCH instead."""
    match = re.search(r'\b(\d{1,6})\b', question)
    return match.group(1) if match else None


def router_node(state: RouterState) -> dict:
    llm = get_llm()
    prompt = ROUTER_PROMPT.format(question=state["question"])
    response = llm.invoke(prompt)
    route = response.content.strip().upper()

    if route not in ("TICKET_LOOKUP", "SEMANTIC_SEARCH", "DIRECT"):
        route = "SEMANTIC_SEARCH"  # safest fallback — search rather than guess

    ticket_id = extract_ticket_id(state["question"]) if route == "TICKET_LOOKUP" else None

    # If it was classified as a lookup but no ID was actually found,
    # fall back to semantic search instead of failing outright.
    if route == "TICKET_LOOKUP" and not ticket_id:
        route = "SEMANTIC_SEARCH"

    print(f"   [Router] → {route}" + (f" (ticket_id={ticket_id})" if ticket_id else ""))
    return {"route": route, "ticket_id": ticket_id}


def ticket_lookup_node(state: RouterState) -> dict:
    driver = get_driver()
    try:
        graph_state = assemble_full_state(driver, state["ticket_id"])
        if not graph_state:
            return {"answer": f"No ticket found with ID {state['ticket_id']}."}

        llm = get_llm()
        answer, _ = generate_resolution(graph_state, llm)
        return {"graph_state": graph_state, "answer": answer}
    finally:
        driver.close()


def semantic_search_node(state: RouterState) -> dict:
    results = search_similar_tickets(state["question"], k=5)
    if not results:
        return {"answer": "I couldn't find any similar past tickets for that."}

    context = "\n\n".join(
        f"[{doc.metadata.get('type', 'text')}] {doc.page_content}" for doc in results
    )

    llm = get_llm()
    prompt = f"""Based on these similar past support cases, answer the
question. Reference specific precedent where relevant.

Similar past cases:
{context}

Question: {state["question"]}

Answer:"""
    response = llm.invoke(prompt)
    return {"search_results": results, "answer": response.content}


def direct_node(state: RouterState) -> dict:
    llm = get_llm()
    response = llm.invoke(state["question"])
    return {"answer": response.content}


def route_decision(state: RouterState) -> str:
    return {
        "TICKET_LOOKUP": "ticket_lookup",
        "SEMANTIC_SEARCH": "semantic_search",
        "DIRECT": "direct",
    }[state["route"]]


def build_graph():
    graph = StateGraph(RouterState)

    graph.add_node("router", router_node)
    graph.add_node("ticket_lookup", ticket_lookup_node)
    graph.add_node("semantic_search", semantic_search_node)
    graph.add_node("direct", direct_node)

    graph.set_entry_point("router")
    graph.add_conditional_edges("router", route_decision, {
        "ticket_lookup": "ticket_lookup",
        "semantic_search": "semantic_search",
        "direct": "direct",
    })
    graph.add_edge("ticket_lookup", END)
    graph.add_edge("semantic_search", END)
    graph.add_edge("direct", END)

    return graph.compile()


def main():
    app = build_graph()
    print("GraphRAG Support Engine ready! Type a question, or 'quit' to exit.\n")

    while True:
        question = input("You: ").strip()
        if question.lower() in ("quit", "exit"):
            break
        if not question:
            continue

        result = app.invoke({"question": question})
        print(f"\nBot: {result['answer']}\n")


if __name__ == "__main__":
    main()