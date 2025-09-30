# Research artefact reference

This guide illustrates the JSON and PDF artefacts produced by the research pipeline so
operators know exactly what to expect when reviewing deliveries or debugging runs.

## Directory structure

All artefacts live under the configured `RESEARCH_ARTIFACT_DIR` and `RESEARCH_PDF_DIR`.
The orchestrator creates run-specific folders using the workflow `run_id`:

```
<RESEARCH_ARTIFACT_DIR>/
  internal_research/<run_id>/internal_research.json
  dossier_research/<run_id>/company_detail_research.json
  similar_companies_level1/<run_id>/similar_companies_level1.json
<RESEARCH_PDF_DIR>/<run_id>/
  company_detail_research.pdf
  similar_companies_level1.pdf
  research_manifest.pdf
```

`research_manifest.pdf` is an optional summary generated when multiple artefacts are
bundled together for CRM delivery. Individual PDFs mirror the JSON fields while
adding human-readable headings and tables.

## Company detail research JSON

The dossier research agent produces a structured JSON report titled "Company Detail
Research". It captures the metadata required to brief event organisers and downstream
CRM teams.

```json
{
  "report_type": "Company Detail Research",
  "run_id": "run-123",
  "event_id": "evt-456",
  "generated_at": "2024-01-01 13:00",
  "company": {
    "name": "Example Corp",
    "domain": "example.com",
    "location": "New York, USA",
    "industry": "Technology",
    "description": "A sample organisation for testing purposes."
  },
  "summary": "Example Corp builds example solutions.",
  "insights": [
    "Revenue grew 25% year over year.",
    "Expanded into two new markets in 2023."
  ],
  "sources": [
    "https://example.com/press",
    "https://news.example.com/article"
  ]
}
```

### PDF layout

The generated PDF renders the same information using the following sections:

1. **Executive summary** – company overview, primary industry, and key value proposition.
2. **Signals & opportunities** – bullet list derived from the `insights` array with
   emphasis on revenue milestones, product launches, or customer wins.
3. **Source appendix** – clickable URLs matching the `sources` array for compliance review.

Headers include the `run_id`, `event_id`, and generation timestamp so auditors can tie
PDFs back to the originating workflow run.

## Similar companies level 1 JSON

The `similar_companies_level1` agent compiles peer organisations that can help with
competitive positioning or cross-sell suggestions.

```json
{
  "company_name": "Example Analytics",
  "run_id": "run-123",
  "event_id": "evt-456",
  "generated_at": "2024-01-01 13:00",
  "results": [
    {
      "id": "1",
      "name": "Example Analytics",
      "domain": "example.com",
      "score": 10.0,
      "matching_fields": ["description", "name", "product", "segment"],
      "properties": {
        "name": "Example Analytics",
        "segment": "Enterprise",
        "product": "Insight Platform",
        "description": "Predictive analytics tools for marketing departments.",
        "domain": "example.com"
      }
    }
  ]
}
```

### PDF layout

The PDF output summarises the `results` array as a ranked table with columns for name,
domain, segment, product, and a bar showing the similarity `score`. A final appendix
captures the detailed `properties` dictionary for each match so operators can copy the
information into CRM records quickly.

## Internal research manifest

When the internal research agent reuses an existing dossier it records the decision in
`internal_research.json` and mirrors the metadata into the run summary. Typical fields
include:

- `status` – `reuse`, `refresh_requested`, or `not_found`.
- `source_artifact` – the absolute path to the prior dossier that was reused.
- `owner` – the last researcher to update the dossier.
- `expires_at` – timestamp formatted as `YYYY-MM-DD HH:MM` (Europe/Berlin) indicating when a
  refresh should be triggered.

If a refresh is required the manifest also lists `reminder_schedule` entries that feed
into the HITL escalation loop.

## CRM delivery expectations

Final deliveries provide both JSON and PDF artefacts:

- Emails generated from `templates/email/final_research_delivery.*` attach the PDFs and
  link to the JSON artefacts using `CRM_ATTACHMENT_BASE_URL` when configured.
- CRM notes reference the same portal links so organisers and sales teams can download
  the dossier bundle without leaving their workflow.
- The run summary stored under `log_storage/run_history/research/workflow_runs/<run_id>/`
  lists every artefact path and delivery status for auditing.

Use these samples to verify that new integrations or custom agents continue to emit
artefacts in the expected format.
