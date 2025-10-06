# Workflow Adjustments Overview

This document summarizes how the research and workflow agents were updated to match the new HubSpot-driven dossier logic.

## Internal Research Agent
- **What changed:** The agent now checks HubSpot for the company and any stored attachments before finishing its run. It saves a short summary of whether the company exists, if attachments are present, and how many were found.
- **Why:** The master workflow needs a consistent signal to decide if a dossier is still required or if the CRM already has relevant files.
- **Resulting behaviour:** Each successful run returns a payload showing `company_in_crm`, `attachments_in_crm`, a derived `requires_dossier` flag, plus basic attachment details.

## Master Workflow Agent
- **What changed:** The hard- and soft-trigger handling now look at the CRM summary returned by the research agent. Hard triggers with CRM attachments route to a human review step. Soft triggers first ask the organizer whether a dossier is needed and, if approved, reuse the hard-trigger flow. The agent also ensures dossier research launches when needed and skips it when CRM already has documents.
- **Why:** This logic mirrors the decision table from the specification and ensures human review steps happen only when attachments already exist.
- **Resulting behaviour:**
  - **Hard trigger + company/attachments present:** The organizer reviews existing CRM files; dossier research runs only if they approve.
  - **Hard trigger + missing company or attachments:** Dossier research starts immediately.
  - **Soft trigger:** The organizer is asked whether to convert to a hard trigger; if they agree, the hard-trigger logic above is reused.

## Human-In-The-Loop Agent
- **What changed:** Confirmation requests now include context about CRM attachments, meeting times, and why the organizer is being contacted. The agent enforces that a communication backend is configured before sending dossier questions and logs audit details for each exchange.
- **Why:** Providing context improves human decisions and prevents silent automation when no email/chat backend is configured.
- **Resulting behaviour:** When prompted, the agent sends a descriptive message to the organizer, records the request/response in the audit log, and returns a clear approval/decline outcome to the master workflow.

