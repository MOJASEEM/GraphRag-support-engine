"""
FastAPI backend for the GraphRAG Support Engine UI.

Wraps router/graph_router.py and returns enough structural detail
(which nodes/relationships were traversed) for the frontend to render
an actual graph visualization, not just a chat bubble.
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from router.graph_router import build_graph

app = FastAPI(title="Support Escalation Engine")
pipeline = build_graph()

STATIC_DIR = Path(__file__).resolve().parent / "static"


class ChatRequest(BaseModel):
    question: str


def build_traversal_trace(result):
    """Converts the raw graph_state into a list of nodes/edges the
    frontend can animate lighting up, in traversal order."""
    nodes = []
    edges = []

    route = result.get("route")
    graph_state = result.get("graph_state")

    if route == "TICKET_LOOKUP" and graph_state:
        ticket = graph_state["ticket"]
        nodes.append({"id": "customer", "label": ticket.get("customer_name") or "Customer", "type": "Customer"})
        nodes.append({"id": "ticket", "label": f"Ticket {ticket['ticket_id']}", "type": "Ticket"})
        nodes.append({"id": "product", "label": ticket.get("product") or "—", "type": "Product"})
        nodes.append({"id": "issue", "label": ticket.get("issue_type") or "—", "type": "IssueType"})

        edges.append({"from": "customer", "to": "ticket", "label": "SUBMITTED"})
        edges.append({"from": "ticket", "to": "product", "label": "ABOUT_PRODUCT"})
        edges.append({"from": "ticket", "to": "issue", "label": "CATEGORIZED_AS"})

        history_count = len(graph_state.get("customer_history", []))
        precedent_count = len(graph_state.get("similar_resolved_tickets", []))

        if history_count > 0:
            nodes.append({"id": "history", "label": f"{history_count} prior ticket(s)", "type": "History"})
            edges.append({"from": "customer", "to": "history", "label": "HAS HISTORY"})

        if precedent_count > 0:
            nodes.append({"id": "precedents", "label": f"{precedent_count} precedent(s)", "type": "Precedent"})
            edges.append({"from": "issue", "to": "precedents", "label": "SIMILAR RESOLVED"})

    return {"nodes": nodes, "edges": edges}


@app.post("/api/chat")
def chat(request: ChatRequest):
    result = pipeline.invoke({"question": request.question})

    trace = build_traversal_trace(result)

    return {
        "answer": result.get("answer", "I wasn't able to generate a response."),
        "route": result.get("route"),
        "trace": trace,
    }


app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")