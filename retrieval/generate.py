"""

Takes the multi-hop graph state from graph/retriever.py and generates
a grounded resolution response — the LLM's job here is root-cause
reasoning across structured signals, not just paraphrasing text.

"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate

from graph.connection import get_driver
from graph.retriever import assemble_full_state, _find_sample_ticket_id

load_dotenv()


PROMPT_TEMPLATE = """You are a Tier-2 Support Escalation Agent. Analyze the
structured case data below and write a clear, grounded resolution response.

CRITICAL INSTRUCTIONS:
- Base your answer ONLY on the data provided below — do not invent details.
- If customer history shows repeat issues, acknowledge that pattern explicitly.
- If similar resolved tickets exist, reference how those were fixed as
  precedent, not just as background.
- If the data is insufficient to determine a root cause, say so clearly
  instead of guessing.

CURRENT TICKET:
Subject: {subject}
Description: {description}
Product: {product}
Issue Type: {issue_type}
Priority: {priority}
Status: {status}

CUSTOMER HISTORY ({history_count} other ticket(s)):
{history_summary}

SIMILAR RESOLVED TICKETS ({precedent_count} found):
{precedent_summary}

Write a resolution response for this ticket, referencing relevant history
or precedent where applicable."""


def get_llm():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is missing. Add a valid Groq API key to the .env file."
        )
    if not api_key.startswith("gsk_"):
        raise RuntimeError(
            "GROQ_API_KEY does not look like a Groq API key. "
            "Replace it with the key copied from console.groq.com."
        )

    return ChatGroq(
        api_key=api_key,
        model=os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"),
        temperature=0.2,
    )


def format_history(history):
    if not history:
        return "No prior tickets from this customer."
    lines = [f"- [{t['ticket_id']}] {t['subject']} ({t['issue_type']}) — {t['status']}"
             for t in history]
    return "\n".join(lines)


def format_precedents(precedents):
    if not precedents:
        return "No similar resolved tickets found for this issue type/product."
    lines = [f"- [{t['ticket_id']}] Resolution: {t['resolution']} (satisfaction: {t['satisfaction_rating']})"
              for t in precedents]
    return "\n".join(lines)


def generate_resolution(state, llm):
    """Takes the assembled graph state (from Step 4) and produces a
    grounded response. Returns (answer_text, state) so callers can
    still access the raw state for hallucination checking later."""
    ticket = state["ticket"]

    prompt = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
    formatted = prompt.format(
        subject=ticket["subject"],
        description=ticket["description"],
        product=ticket["product"],
        issue_type=ticket["issue_type"],
        priority=ticket["priority"],
        status=ticket["status"],
        history_count=len(state["customer_history"]),
        history_summary=format_history(state["customer_history"]),
        precedent_count=len(state["similar_resolved_tickets"]),
        precedent_summary=format_precedents(state["similar_resolved_tickets"]),
    )

    response = llm.invoke(formatted)
    return response.content, state


def main():
    driver = get_driver()
    llm = get_llm()

    try:
        sample_id = _find_sample_ticket_id(driver)
        if not sample_id:
            print("No tickets found — did you run ingestion/load_graph.py first?")
            return

        print(f"Generating resolution for ticket: {sample_id}\n")
        state = assemble_full_state(driver, sample_id)

        answer, _ = generate_resolution(state, llm)

        print("=" * 50)
        print("GENERATED RESOLUTION")
        print("=" * 50)
        print(answer)

    finally:
        driver.close()


if __name__ == "__main__":
    main()