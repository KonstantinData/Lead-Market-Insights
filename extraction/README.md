# Extraction module

This package houses specialised data extraction utilities that enrich raw calendar events
with the context required by downstream systems (e.g., CRM dossiers).

## Current components

| File | Description |
|------|-------------|
| [`extractor.py`](extractor.py) | Placeholder class demonstrating how to parse raw event payloads and return the structured fields needed by the broader workflow. |

## Extending extraction logic

* Implement domain-specific parsers that derive additional metadata from event
  descriptions, attachments, or linked systems.
* Add validation layers to flag incomplete data before it reaches the human-in-the-loop
  agents.
* Coordinate with [`agents/extraction_agent.py`](../agents/extraction_agent.py) to ensure the
  extracted schema matches what the master workflow expects.
