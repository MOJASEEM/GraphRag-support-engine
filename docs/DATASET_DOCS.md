# Dataset Notes

## Chosen: Customer Support Ticket Dataset (Kaggle)

**Source:** Kaggle — search "Customer Support Ticket Dataset"
**Format:** Single flat CSV

## Why this dataset

- Purpose-built for support escalation — not a repurposed reviews or
  complaints dataset adapted to fit.
- English text throughout — Ticket Description, Resolution fields.
- Includes real operational metrics (First Response Time, Time to
  Resolution, Customer Satisfaction Rating) — feeds the "impact framing"
  step later with genuine numbers, not invented ones.
- Both problem text (Ticket Description) AND outcome text (Resolution)
  are available — lets the system reason about both "what went wrong"
  and "how similar issues were solved."

## Honest limitation

This is a single flat CSV, not a relational database with foreign keys.
The graph structure here is DERIVED from categorical columns (Product,
Ticket Type, Channel). This is a genuinely
different (and worth-explaining) design situation: most real production
graphs are built by identifying meaningful relationships in otherwise
flat/tabular data, not just importing an existing schema — arguably a
more representative interview talking point than Olist would have been.

## Schema

(:Customer)-[:SUBMITTED]->(:Ticket)
(:Ticket)-[:ABOUT_PRODUCT]->(:Product)
(:Ticket)-[:CATEGORIZED_AS]->(:IssueType)
(:Ticket)-[:VIA_CHANNEL]->(:Channel)

Unstructured text → Ticket Description + Resolution, both embedded
separately (tagged by type) into the vector index.