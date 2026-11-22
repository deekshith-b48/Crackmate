# Changelog

All notable changes to CrackMate. Dates are when the work landed on `main`.

## Unreleased

### Added
- **Claude and Codex support (MCP).** Your own AI assistant can write lessons and score answers, so no API key is needed. New tools: `create_profile`, `save_profile`, `attach_repo`, `prepare_lesson`, `save_lesson`, `prepare_grading`, `save_grading`. See [docs/connect-ai-assistants.md](docs/connect-ai-assistants.md).
- **Claude Code plugin** with a coaching skill, and a launcher script (`scripts/mcp.sh`) that sets itself up on first run.
- **Backup AI provider.** When Groq is rate limited, CrackMate switches to any OpenAI-compatible provider (`ALT_LLM_*` settings), for example Google AI Studio.
- **"Add another resume"** button under the profile selector.
- **Docker image** published to GitHub Packages, and a `CRACKMATE_PORT` setting for when port 8000 is taken.
- **New README** with separate Manual and Claude/Codex/MCP setup paths, diagrams and an API key guide.

### Changed
- **Brand theme.** New logo, dark purple theme with a light option, and a responsive layout from phone to wide screens.
- Pages refresh when you return to the tab, so work done in your assistant shows up on the website.
- The dashboard says "Early signal" until several topics are assessed, instead of "Strong" after one answer.

### Fixed
- Pitch and Claim Checker failing with "did not return a valid result": cut-off answers are retried with more room, and an unusable answer moves on to the next model.
- Items written by the backup provider wrongly showing "Outdated".
- Ask CrackMate adopting a persona found in your repos (it called itself "Qivra"). It now always answers as CrackMate and shows only sources it cites.
- The MCP server refusing to start when no profile existed yet.
- A "Start with your resume" flash while the profile was still loading.

## 0.1.0

First public release: resume to profile, project and skill lessons, claim checker, pitch, architecture diagrams, spaced repetition, voice mock interview, career intelligence from your GitHub repos, study plan, command line and a first MCP server.
