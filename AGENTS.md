# Codex project instructions

## Project profile

- Engineering conventions (domains, verification commands, acceptance gate, architecture boundaries) live in the `## 工程档案` section of `CLAUDE.md`. Read it before changing code.
- Hardware rules follow the official sources recorded in `docs/official-comparison.md`; do not port SO-ARM101 workbench behaviour without checking it against the `openarm_mini` driver.

## Shared knowledge

- Read `agent_wiki/AGENTS.md` before creating or updating durable project knowledge.
- User-visible behaviour is described in `feature_wiki/`.
