
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from graph.connection import get_driver


def get_ticket_full_context(driver, ticket_id):
    """1-hop out from a single ticket: who submitted it, what product,
    what issue type, what channel. This is the 'assemble the full
    picture for one case' query."""
    query = """
    MATCH (t:Ticket)
    WHERE toString(t.ticket_id) = toString($ticket_id)
    OPTIONAL MATCH (c:Customer)-[:SUBMITTED]->(t)
    OPTIONAL MATCH (t)-[:ABOUT_PRODUCT]->(p:Product)
    OPTIONAL MATCH (t)-[:CATEGORIZED_AS]->(i:IssueType)
    OPTIONAL MATCH (t)-[:VIA_CHANNEL]->(ch:Channel)
    RETURN t.ticket_id AS ticket_id,
           t.subject AS subject,
           t.description AS description,
           t.status AS status,
           t.resolution AS resolution,
           t.priority AS priority,
           t.satisfaction_rating AS satisfaction_rating,
           c.name AS customer_name,
           c.email AS customer_email,
           p.name AS product,
           i.name AS issue_type,
           ch.name AS channel
    """
    with driver.session() as session:
        result = session.run(query, ticket_id=ticket_id)
        record = result.single()
        return dict(record) if record else None


def get_customer_ticket_history(driver, customer_email, exclude_ticket_id=None):
    """2-hop: Customer -> all their OTHER tickets. Answers 'has this
    person had issues before, and were they resolved?' — the kind of
    context a human agent would want before responding."""
    query = """
    MATCH (c:Customer {email: $email})-[:SUBMITTED]->(t:Ticket)
    WHERE $exclude_id IS NULL OR t.ticket_id <> $exclude_id
    OPTIONAL MATCH (t)-[:CATEGORIZED_AS]->(i:IssueType)
    RETURN t.ticket_id AS ticket_id,
           t.subject AS subject,
           t.status AS status,
           i.name AS issue_type
    ORDER BY t.ticket_id
    """
    with driver.session() as session:
        result = session.run(query, email=customer_email, exclude_id=exclude_ticket_id)
        return [dict(record) for record in result]


def get_similar_resolved_tickets(driver, issue_type, product=None, limit=5):
    """This is the highest-value query in the whole system: given an
    issue type (and optionally a product), find OTHER tickets with the
    same category that were actually closed, and return how they were
    resolved. This is precedent-based reasoning — 'here's how we fixed
    this exact kind of problem before' — something plain vector search
    over descriptions alone wouldn't reliably surface."""
    query = """
    MATCH (t:Ticket)-[:CATEGORIZED_AS]->(i:IssueType {name: $issue_type})
    WHERE t.status = 'Closed' AND t.resolution <> ''
    """
    if product:
        query += """
        MATCH (t)-[:ABOUT_PRODUCT]->(p:Product {name: $product})
        """
    query += """
    RETURN t.ticket_id AS ticket_id,
           t.subject AS subject,
           t.resolution AS resolution,
           t.satisfaction_rating AS satisfaction_rating
    ORDER BY t.satisfaction_rating DESC
    LIMIT $limit
    """
    with driver.session() as session:
        result = session.run(query, issue_type=issue_type, product=product, limit=limit)
        return [dict(record) for record in result]


def assemble_full_state(driver, ticket_id):
    """The main entry point for Step 5 (generation) to call. Combines
    all three traversals above into one 'state' object — this is the
    graph equivalent of the retrieved chunks in a normal RAG pipeline."""
    ticket_context = get_ticket_full_context(driver, ticket_id)
    if not ticket_context:
        return None

    history = get_customer_ticket_history(
        driver, ticket_context["customer_email"], exclude_ticket_id=ticket_id
    )

    precedents = get_similar_resolved_tickets(
        driver, ticket_context["issue_type"], product=ticket_context["product"]
    )

    return {
        "ticket": ticket_context,
        "customer_history": history,
        "similar_resolved_tickets": precedents,
    }


def _find_sample_ticket_id(driver):
    """Test helper — grabs a real ticket ID from your graph so you don't
    have to look one up manually."""
    query = "MATCH (t:Ticket) RETURN t.ticket_id AS ticket_id LIMIT 1"
    with driver.session() as session:
        record = session.run(query).single()
        return record["ticket_id"] if record else None


def main():
    driver = get_driver()
    try:
        sample_id = _find_sample_ticket_id(driver)
        if not sample_id:
            print("No tickets found — did you run ingestion/load_graph.py first?")
            return

        print(f"Testing multi-hop retrieval on ticket: {sample_id}\n")

        state = assemble_full_state(driver, sample_id)

        print("=" * 50)
        print("TICKET CONTEXT")
        print("=" * 50)
        for k, v in state["ticket"].items():
            print(f"  {k}: {v}")

        print(f"\n{'=' * 50}")
        print(f"CUSTOMER HISTORY ({len(state['customer_history'])} other ticket(s))")
        print("=" * 50)
        for t in state["customer_history"]:
            print(f"  [{t['ticket_id']}] {t['subject']} — {t['status']}")

        print(f"\n{'=' * 50}")
        print(f"SIMILAR RESOLVED TICKETS ({len(state['similar_resolved_tickets'])} found)")
        print("=" * 50)
        for t in state["similar_resolved_tickets"]:
            print(f"  [{t['ticket_id']}] Resolution: {t['resolution'][:100]}...")

    finally:
        driver.close()


if __name__ == "__main__":
    main()