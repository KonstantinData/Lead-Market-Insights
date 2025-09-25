# Human-in-the-Loop Module

**Status**: Implemented in `agents/human_in_loop_agent.py`

This functionality is now part of the main agent-based architecture. Human-in-the-loop validation and manual input handling is managed by the `HumanInLoopAgent` which is orchestrated by the `MasterWorkflowAgent`.

## Current Implementation

- **Location**: `agents/human_in_loop_agent.py`
- **Usage**: Automatically invoked by `MasterWorkflowAgent.run_workflow()`
- **Purpose**: Handle manual validation and completion of incomplete information

## Key Features

- Interactive prompts for missing information
- User input validation
- Integration with extraction workflow
- Fallback handling for automation gaps

## Workflow Integration

The Human-in-the-Loop agent is triggered when:
1. `ExtractionAgent` identifies incomplete information
2. Manual validation is required for extracted data
3. System needs user confirmation for processing decisions

## Usage Example

When the system detects missing company information, it will prompt:
```
Please provide missing info for event 1: {'company_name': None, 'web_domain': None}
```

For implementation details, see the `HumanInLoopAgent` class in the agents module.
