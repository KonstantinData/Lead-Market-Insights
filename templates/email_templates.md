# Email Templates

**Status**: Template infrastructure available

This module provides template management for email and other communication components within the agent-based workflow system.

## Current Implementation

- **Location**: `templates/` directory
- **Usage**: Can be integrated with agents that require communication functionality
- **Purpose**: Centralized template management for consistent messaging

## Integration with Agent Architecture

Templates can be used by:
- **HumanInLoopAgent**: For formatting user prompts and interactions
- **Email notifications**: If implemented as part of workflow completion
- **CRM integration**: For standardized communication with external systems

## Template Types

Future templates might include:
- User input request templates
- Event processing notifications
- Error and status reporting
- Integration confirmation messages

## Usage Pattern

Templates should follow the established agent pattern and integrate with the `MasterWorkflowAgent` orchestration when communication functionality is needed.
