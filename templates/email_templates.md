# Email Templates

This directory stores reusable communication snippets shared across agents.

## Internal research: existing dossier notification
- **Text template:** `templates/email/internal_research_existing_dossier.txt`
- **HTML template:** `templates/email/internal_research_existing_dossier.html`
- **Purpose:** informs requestors that a dossier already exists and provides a portal link back to the CRM attachment.

## Internal research: final research delivery
- **Text template:** `templates/email/final_research_delivery.txt`
- **HTML template:** `templates/email/final_research_delivery.html`
- **Purpose:** delivers the completed dossier with PDF attachments or directs the recipient to the CRM portal link when attachments are hosted externally.

Both template pairs expect the following context keys when rendered:

| Key | Description | Notes |
| --- | ----------- | ----- |
| `recipient_name` | Friendly name for the recipient. | Typically the local-part of the email address. |
| `company_name` | Target company covered by the dossier. | | 
| `last_report_date` | (Existing dossier template only) ISO-formatted or human readable date of the current dossier. | |
| `highlights` | (Final delivery template only) Bullet list or paragraph summarising key insights. | Optional; renderers may pass an empty string. |
| `signature` | Signature block (text or HTML). | Defaults provided by `InternalResearchAgent`. |

Templates fall back gracefully when optional context values are omitted thanks to safe-formatting helpers in the agent code.
