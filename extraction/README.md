# Extraction Module

**Status**: Implemented in `agents/extraction_agent.py`

This functionality is now part of the main agent-based architecture. Information extraction from calendar events is handled by the `ExtractionAgent` which is orchestrated by the `MasterWorkflowAgent`.

## Current Implementation

- **Location**: `agents/extraction_agent.py`
- **Usage**: Automatically invoked by `MasterWorkflowAgent.run_workflow()`
- **Purpose**: Extract required information fields from calendar events

## Key Features

- Company name extraction from event content
- Web domain identification
- Completeness validation of extracted information
- Structured data output for downstream processing

## Integration Points

The extraction agent integrates with:
- **TriggerDetectionAgent**: Processes events that match trigger criteria
- **HumanInLoopAgent**: Requests manual input for incomplete extractions
- **Logging system**: Records extraction results and errors

For implementation details, see the `ExtractionAgent` class in the agents module.
