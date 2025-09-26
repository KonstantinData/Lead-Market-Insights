# Log storage directory

This directory is reserved for runtime log artefacts produced by the workflow
agents. By default the configuration stores run outputs under
`log_storage/run_history`, separating generated files from the repository root.

> **Note:** The directory is kept in version control with a placeholder file so
> that fresh clones have a consistent location for log output. Actual log files
> can be safely deleted or ignored as needed.
