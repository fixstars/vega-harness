# Attribution

This directory is a fork of `skill-creator` from **anthropics/skills**.

- Source: https://github.com/anthropics/skills (path: `skills/skill-creator`)
- Upstream commit: `34040c9c568585f6929bedeaad110ad08f079624` (2026-09-10)
- License: Apache-2.0 (see `LICENSE.txt`)

## Modifications by Fixstars Corporation (Vega harness)

For OpenCode + open-weight LLM deployments:

- `scripts/run_eval.py`: Claude Code CLI (`claude -p`, `.claude/commands/`, stream-json events)
  replaced with OpenCode (`opencode run --format json`, `.agents/skills/`, JSON tool events)
- `scripts/improve_description.py`: `claude -p` replaced with `opencode run`
- `SKILL.md`, `eval-viewer/viewer.html`, `references/schemas.md`: harness-neutral wording
- `SKILL.md`: added a line telling the agent to respond in the user's language
- `scripts/generate_report.py`: wording
