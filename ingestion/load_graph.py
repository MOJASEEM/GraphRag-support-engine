"""
ingestion/load_graph.py

Loads the Customer Support Ticket Dataset (flat CSV) into Neo4j as a
graph, deriving node/relationship structure from categorical columns
since this dataset has no pre-existing foreign-key relationships.

Column names assumed (adjust to match your actual CSV header if it
differs slightly — run `df.columns.tolist()` first to check):
  Ticket ID, Customer Name, Customer Email, Customer Age, Customer Gender,
  Product Purchased, Ticket Type, Ticket Subject, Ticket Description,
  Ticket Status, Resolution, Ticket Priority, Ticket Channel,
  First Response Time, Time to Resolution, Customer Satisfaction Rating

Run with:  python ingestion/load_graph.py
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

import pandas as pd
from graph.connection import get_driver

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
CSV_FILENAME = "customer_support_tickets.csv"  # rename to match your download


def load_csv():
    print("Loading CSV...")
    df = pd.read_csv(DATA_DIR / CSV_FILENAME)
    print(f"   {len(df)} ticket(s) loaded.")
    print(f"   Columns found: {df.columns.tolist()}")
    return df


def create_constraints(driver):
    print("Creating constraints...")
    constraints = [
        "CREATE CONSTRAINT customer_email IF NOT EXISTS FOR (c:Customer) REQUIRE c.email IS UNIQUE",
        "CREATE CONSTRAINT ticket_id IF NOT EXISTS FOR (t:Ticket) REQUIRE t.ticket_id IS UNIQUE",
        "CREATE CONSTRAINT product_name IF NOT EXISTS FOR (p:Product) REQUIRE p.name IS UNIQUE",
        "CREATE CONSTRAINT issue_type IF NOT EXISTS FOR (i:IssueType) REQUIRE i.name IS UNIQUE",
        "CREATE CONSTRAINT channel_name IF NOT EXISTS FOR (ch:Channel) REQUIRE ch.name IS UNIQUE",
    ]
    with driver.session() as session:
        for c in constraints:
            session.run(c)


def load_customers(driver, df):
    print("Loading customers...")
    rows = df[["Customer Email", "Customer Name", "Customer Age", "Customer Gender"]] \
        .drop_duplicates(subset="Customer Email") \
        .fillna("") \
        .to_dict("records")

    query = """
    UNWIND $rows AS row
    MERGE (c:Customer {email: row.`Customer Email`})
    SET c.name = row.`Customer Name`,
        c.age = row.`Customer Age`,
        c.gender = row.`Customer Gender`
    """
    with driver.session() as session:
        session.run(query, rows=rows)


def load_tickets_and_relationships(driver, df):
    print("Loading tickets + all relationships...")
    rows = df.fillna("").to_dict("records")

    # Single query per ticket row handles the ticket node AND all four
    # relationships (customer, product, issue type, channel) at once —
    # more efficient than four separate passes over the same data.
    query = """
    UNWIND $rows AS row
    MERGE (t:Ticket {ticket_id: row.`Ticket ID`})
    SET t.subject = row.`Ticket Subject`,
        t.description = row.`Ticket Description`,
        t.status = row.`Ticket Status`,
        t.resolution = row.Resolution,
        t.priority = row.`Ticket Priority`,
        t.first_response_time = row.`First Response Time`,
        t.time_to_resolution = row.`Time to Resolution`,
        t.satisfaction_rating = row.`Customer Satisfaction Rating`

    WITH t, row
    MATCH (c:Customer {email: row.`Customer Email`})
    MERGE (c)-[:SUBMITTED]->(t)

    WITH t, row
    MERGE (p:Product {name: row.`Product Purchased`})
    MERGE (t)-[:ABOUT_PRODUCT]->(p)

    WITH t, row
    MERGE (i:IssueType {name: row.`Ticket Type`})
    MERGE (t)-[:CATEGORIZED_AS]->(i)

    WITH t, row
    MERGE (ch:Channel {name: row.`Ticket Channel`})
    MERGE (t)-[:VIA_CHANNEL]->(ch)
    """
    with driver.session() as session:
        session.run(query, rows=rows)


def main():
    df = load_csv()

    driver = get_driver()
    try:
        create_constraints(driver)
        load_customers(driver, df)
        load_tickets_and_relationships(driver, df)
        print("\n✅ Graph loaded successfully.")
        print("Test query to try in the Neo4j Aura browser:")
        print("  MATCH (c:Customer)-[:SUBMITTED]->(t:Ticket)-[:CATEGORIZED_AS]->(i:IssueType)")
        print("  RETURN c, t, i LIMIT 25")
    finally:
        driver.close()


if __name__ == "__main__":
    main()