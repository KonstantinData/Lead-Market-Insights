# Changelog

## Unreleased

### Added
- Domain validation guard to block placeholder or invalid extraction domains before research dispatch.
- Semantic status normalisation for similar company and dossier research outputs.
- Atomic JSON persistence with schema validation for run indices and processed events.

### Fixed
- Prevented corrupt JSON warnings by writing state files atomically and validating against schemas.
