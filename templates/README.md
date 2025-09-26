# Templates

Communication templates centralise the wording used by agents when contacting organisers,
stakeholders, or administrators.  Keeping templates in a dedicated package makes it easy to
update messaging without touching the automation logic. When adjusting messaging, review the
masking and approval requirements documented in [`docs/compliance.md`](../docs/compliance.md).

## Contents

| File | Purpose |
|------|---------|
| [`email_templates.md`](email_templates.md) | Reference collection of subject/body patterns for reminders, escalations, and dossier confirmation requests. |

Feel free to add additional markdown, text, or HTML files to this package as the workflows
expand to cover more communication channels.

## Prompt change management

Prompt definitions live in [`prompts/`](prompts) with explicit semantic version tags. Each
prompt file must include a metadata block documenting temperature, token budgets, authorship,
and a short changelog entry so operators can audit revisions quickly.

When updating prompts:

1. Introduce a new file with an incremented `version` field instead of editing an existing
   one. This preserves the history of previous variants for reproducibility.
2. Record the rationale for the change in the `metadata.changelog` entry.
3. Update configuration or environment overrides if consumers should adopt the new version
   immediately; otherwise the loader will continue serving the prior default.

### Rollback procedure

To roll back to an earlier prompt:

1. Set the appropriate `PROMPT_VERSION_<PROMPT_NAME>` environment variable (or the matching
   entry in the shared agent configuration file) to the desired version tag.
2. Restart the affected services so they pick up the refreshed configuration. No file
   changes are required because each version remains on disk.
3. Once the incident is resolved, evaluate whether the newer prompt should be revised or
   deprecated.
