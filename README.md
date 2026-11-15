<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="web/public/brand/wordmark-dark.png">
    <img src="web/public/brand/wordmark-light.png" alt="CrackMate" width="320">
  </picture>
</p>

# CrackMate

**Free, open-source interview preparation.** CrackMate turns a reviewed resume (and the real code of your projects) into interview lessons, practice feedback, spaced-repetition review and a time-boxed study plan. It runs on your computer, uses your own free Groq key for generation, and never helps during a real live interview: it is for preparation and mock practice only.

## What you get

| Area | What it does |
|---|---|
| **Setup** | Read a resume, review the extracted profile and projects before anything is sent to a model. |
| **Learn** | Project deep-dives, skill lessons, claim checker, 2-minute pitch, follow-up ladders, Mermaid architecture diagrams, knowledge library with citations, company DSA mode, study wiki. |
| **Practice** | Question cards with spaced repetition (SM-2), practice with feedback, voice mock interview, study-first queue, interview brief. |
| **Analyse** | Skill knowledge graph, interview-risk scores, blast radius, built-vs-claimed, talking points, security scan, engineering decisions mined from your git history. |
| **Plan / Track** | Time-boxed preparation plan, adaptive plan, readiness and progress. |
| **System** | Ask CrackMate (answers cited to your own sources), usage and free-tier headroom. |

Also included: a command line (`./crackmate_cli`) and an MCP server so you can study from Claude or any MCP host.

## Quick start

```sh
# 1. Python 3.13 environment
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt -r requirements-api.txt

# 2. Add your free Groq key (https://console.groq.com) to a file that is never committed
mkdir -p .streamlit
printf 'GROQ_API_KEY = "your-key-here"\n' > .streamlit/secrets.toml

# 3. Run (builds the web app on first run; needs Node 20+ and npm)
./run.sh        # then open http://127.0.0.1:8000
```

**Rate limits?** Groq's free tier is limited per minute and per day. In `.streamlit/secrets.toml` you can add `GROQ_FALLBACK_MODEL = "openai/gpt-oss-120b"` (a second quota on the same key) and an optional second provider, used automatically when Groq is busy: `ALT_LLM_API_KEY`, `ALT_LLM_BASE_URL` and `ALT_LLM_MODEL` for any OpenAI-compatible endpoint (for example Google AI Studio). Voice transcription always uses Groq Whisper.

## Project layout

| Folder | Purpose |
|---|---|
| `core/` | The engine: models and retries, lessons and shared cache, spaced repetition, career intelligence (`core/career/`), knowledge search (`core/ask/`), storage. No UI code. |
| `api/` | FastAPI backend (loopback only, Host/Origin checks, streamed generation). |
| `web/` | Next.js interface (static export, Tailwind, dark purple brand theme with a light option, responsive from phone to wide screens). |
| `crackmate/`, `crackmate_cli` | Command line and MCP server. |
| `ui/`, `app.py` | The original Streamlit interface, still supported. |
| `prompts/`, `tests/` | Prompt templates and the Python test suite. |

## Privacy and honesty

Your key stays in `.streamlit/secrets.toml` and is never sent to the browser. Data lives in `.crackmate/` on your machine. Lessons that are not tied to a source are labelled as general model knowledge, and claims about your code are only made with evidence. Credit and licences of any bundled knowledge are listed under Privacy and storage below.

## New interface (Next.js + FastAPI)

A modern web interface sits on top of the same Python engine. Your data, key and lessons are shared with the Streamlit app below, so you can use either.

```sh
.venv/bin/python -m pip install -r requirements.txt -r requirements-api.txt
./run.sh
```

`run.sh` builds the web app on its first run (needs Node 20 or newer and npm, about 700 MB in `web/node_modules`), then serves everything at [http://127.0.0.1:8000](http://127.0.0.1:8000). There is no Node process at runtime.

- **Workflow:** Home, Setup, Learn, Practice, Plan and Track. The sidebar follows how you prepare: set up once, learn, practise out loud, plan the last hours, then track progress.
- **Live progress:** every generation shows a step checklist instead of a blank spinner. Question cards hide the answer first. Press Space to reveal and 1 to 4 to rate (Again, Hard, Good, Easy).
- **Voice:** record in the browser. It is converted to 16 kHz WAV in the page, so ffmpeg is not needed. Audio goes to Groq only when you press Transcribe and is never saved.
- **Security:** the API listens on loopback only, rejects unexpected Host and Origin headers, requires a custom header on writes, and never sends your Groq key to the browser.
- **Developing:** run `.venv/bin/python -m uvicorn api.main:app --port 8000` and, in `web/`, `npm run dev`, then open http://127.0.0.1:3000. Set `CRACKMATE_DB=/path/to/copy.sqlite3` to try the app on a copy of your data. Tests: `.venv/bin/python -m unittest discover -s tests` and `cd web && npm test`.
- **Not yet in the new interface:** the topic catalogue editor, the diagnostic quiz and attempt comparison. Use the Streamlit app for those.

### Career intelligence (new)

CrackMate can now read the real code behind a project. On **Learn → Projects**, paste a public GitHub repository URL and it will, with no model calls:

- detect your stack from dependency files, imports and config (each finding shows how sure it is),
- check resume claims against the code: technologies claimed but not found, and found but not claimed,
- work out how much of the code you wrote, and which files you will be asked about but did not write,
- find hotspots (the most-changed files) as talking points for "a challenge I solved",
- scan for committed secrets (values are masked and never stored).

It also builds a skill knowledge graph and per-topic **readiness (1-10)** and **interview risk (0-10)** scores from your practice and review history (API: `/api/profiles/{id}/career/...`). Repositories are downloaded shallow into `.crackmate/repos/`, re-read only when the commit changes, and deleted when you remove them. Set `CRACKMATE_REPOS` to store them elsewhere.

**Ask CrackMate and the Interview Brief.** *System → Ask CrackMate* answers questions using only your resume, the code of your attached repositories, your saved lessons and the knowledge base, streams the answer, and numbers every claim so you can open the exact source. It uses keyword (BM25) search over a private per-profile index that rebuilds only the part that changed; there are no embeddings and no extra downloads. If the sources do not contain the answer it says so, and any general guidance is labelled. *Practice → Interview brief* gathers your pitches, top risks, claims to defend, decisions and key answers into one downloadable Markdown file, with no model call. *System → Usage* shows model calls, cache savings and free-tier headroom.

### Command line and MCP

```sh
./crackmate_cli init --resume resume.pdf --repo https://github.com/you/project   # profile + repo, asks before sending the resume to Groq
./crackmate_cli next        # the single best thing to study right now
./crackmate_cli risk        # your top interview-risk topics
./crackmate_cli quiz --topic caching   # terminal flashcards with spaced repetition
./crackmate_cli update      # re-read attached repos, only if their commit changed
./crackmate_cli brief -o brief.md      # your Interview Brief
./crackmate_cli serve       # the web app and API
./crackmate_cli profiles    # list profiles (use --profile <id> on other commands)
```

**MCP server.** `./crackmate_cli mcp` starts a stdio MCP server so you can study inside Claude or any MCP host. Tools: `get_profile`, `get_overview`, `get_lesson`, `quiz_me`, `grade_answer`, `get_weak_spots`, `get_study_next`, `get_project_architecture`, `search_knowledge` (every result has a source to cite) and `get_interview_brief`. Only `grade_answer` calls a model (your Groq key) and saves a practice attempt; the rest read local data. Add it to Claude Desktop (use your own folder path) with:

```json
{ "mcpServers": { "crackmate": { "command": "/path/to/Crackmate/crackmate_cli", "args": ["mcp"] } } }
```

or, in Claude Code, `claude mcp add crackmate -- /path/to/Crackmate/crackmate_cli mcp`. Set `CRACKMATE_PROFILE` to pick a profile other than the newest. For preparation and mock practice only, never during a real interview.

## Setup (Streamlit interface)

Use Python 3.13 and a recent browser. Open a terminal in this source directory and run the following on macOS or Linux.

```sh
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

On Windows PowerShell, use the following commands.

```powershell
py -3.13 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m streamlit run app.py
```

Open [CrackMate on localhost](http://127.0.0.1:8501/). The app binds to loopback. Stop it with Ctrl+C.

Tested with Python 3.13.9 on macOS, Streamlit 1.67.0, pypdf 7.1.0, Pydantic 2.14.3 and Groq SDK 1.7.0. The bundled SQLite version was 3.50.4.

### Configure Groq

Create a key in the [Groq Console](https://console.groq.com/keys). Store it in `.streamlit/secrets.toml` in this directory and restart the app.

```toml
GROQ_API_KEY = "your-key-here"
GROQ_MODEL = "openai/gpt-oss-20b"
# GROQ_FALLBACK_MODEL = "openai/gpt-oss-120b"
# Optional second provider, used automatically when Groq is rate limited (any OpenAI-compatible endpoint):
# ALT_LLM_API_KEY = "..."
# ALT_LLM_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
# ALT_LLM_MODEL = "gemini-3.5-flash"
```

You can also export the variables in your shell. Environment variables take precedence. For macOS or Linux, copy `.env.example` to `.env`, fill in the values, and load the trusted local file before launch.

```sh
cp .env.example .env
# Edit .env in your editor, then run:
set -a
source ./.env
set +a
python -m streamlit run app.py
```

The app reads the environment and Streamlit secrets. It does not automatically load `.env`. Never paste your key into the resume or commit it to source control.

The documented default supports chat JSON mode and is listed in Groq’s free plan limits. Availability and quotas depend on your account. Choose a supported chat JSON model available to your project if the default fails. The fallback is optional and is used for unavailable models. CrackMate never enables billing. Requests follow your Groq account’s plan and limits. [Groq models](https://console.groq.com/docs/models) · [JSON mode](https://console.groq.com/docs/structured-outputs) · [Rate limits](https://console.groq.com/docs/rate-limits)

## Prepare for an interview

1. **Resume and profile.** Paste resume text or read a PDF or UTF-8 LaTeX file into the editable preview. Remove personal details, confirm the Groq transfer, and extract a profile. A blank profile supports manual entry without a key. Save corrections to skills and projects before generating material.
2. **Projects.** Choose a project and clarify what you built. Add only the relevant README excerpt or code. Generate one section at a time, from project story through engineering decisions. Review the assumptions and open the answers as needed.
3. **Skills.** Pick a resume skill or core topic at Basics, Intermediate or Advanced. Data structures and algorithms lessons include a worked Python problem and complexity assumptions. Mark lessons complete to track progress.
4. **Practice.** Choose a current lesson and work through three questions one at a time. Reveal a hint or an example answer, or submit your own answer for rubric-based feedback. Past attempts are available under Attempt history. Scores are coaching estimates.
5. **Preparation plan.** Enter the interview time in your computer’s local time, your available study hours and weak areas. The app schedules up to 24 study hours in blocks of up to 50 minutes, with ten-minute breaks, 23:00–07:00 reserved for sleep and a 15-minute interview buffer. The model assigns activities to app-validated windows. Use **Open relevant lesson** to jump to linked material.
6. **Export.** Download a lesson, project, plan or all material from the active profile. Project exports identify incomplete sections. Saved material based on earlier inputs is marked outdated.

## Extra preparation tools

- **Claim Checker.** Turns resume claims into the questions an interviewer is most likely to ask, ranked by risk. Tick the ones you can defend out loud. Ticks are saved locally and reset when you re-check after a profile change.
- **Project Pitch.** A spoken-style 2-minute pitch per project to rehearse.
- **Architecture.** A likely architecture diagram per project. Dashed nodes are assumptions. The picture loads Mermaid from a CDN, so it needs internet access.
- **Question cards and Review today.** Answers stay hidden until you reveal them. Rate yourself and an SM-2 schedule decides when the question returns. Each revealed card can build a follow-up ladder: why, how, what if it fails, how does it scale.
- **Faster generation.** `GROQ_FAST_MODEL` (default `openai/gpt-oss-20b`) handles extraction and scoring, while `GROQ_MODEL` handles teaching. Rate limits retry with backoff and then try the next model. **Generate all missing sections** runs project sections three at a time.

- **Shared lesson cache and pre-generated topics.** Skill lessons are generic by default (topic and level only, no resume data), so one generated lesson is reused by every profile on this installation without another Groq call. **Tailor to my resume** rewrites a lesson with your stack and target role and keeps it private to your profile. Project sections are never shared. Prepare 50 common topics once with `.venv/bin/python -m core.pregen` (add `--levels Basics Intermediate Advanced` for more). It needs your Groq key, skips finished lessons, and on free limits can take a while. Shared lessons cite knowledge-base sources, so if you ever copy them out, keep the source credits and licenses.

All of this is generated practice material. Questions are most likely, never guaranteed.

## Privacy and storage

The resume preview and original upload are held in the browser session and Streamlit memory. The SQLite database in `.crackmate/preparation.sqlite3` stores reviewed profiles, clarifications, validated model results, progress and practice attempts. Private files are ignored by Git. The database is local plaintext. Keep the project directory private and use the app on loopback for your own preparation.

Extracting a profile sends the edited text to Groq after confirmation. Later actions send the context needed for that lesson, plan or feedback. Review project snippets, target details and practice answers before sending them. See [Groq’s data documentation](https://console.groq.com/docs/your-data) for provider handling.

Saved lessons are reused for the same inputs, prompt/schema and model settings. **Regenerate** explicitly replaces a result after successful validation. Profile edits only make affected lessons outdated. Plans also reflect recent practice and study resources.

To delete data, select the profile, open **Resume and profile → Delete this preparation profile**, check the confirmation box and click **Delete profile**. This removes the profile and its saved content, cache, attempts and progress from SQLite. Manage downloaded Markdown, backups and provider data separately. Exports omit the raw resume, internal prompts and practice transcripts. Common email and phone patterns are redacted. Review an export before sharing it.

## Troubleshooting

- **PDF has no readable text.** Use a text-based PDF, UTF-8 `.tex` or pasted text. Encrypted files need to be unlocked first. LaTeX and uploaded code are read as text. OCR and compilation are outside Phase 1.
- **Input limit.** Defaults are 5 MB, 10 PDF pages and 12,000 extracted characters. Set `CRACKMATE_MAX_FILE_MB`, `CRACKMATE_MAX_PAGES` and `CRACKMATE_MAX_TEXT_CHARS` through the environment or secrets. The allowed ranges are 1–50 MB, 1–100 pages and 1–40,000 characters. Provider token limits can be lower for a particular request. Shorten the relevant excerpt if Groq rejects its size.
- **Key rejected or model unavailable.** Verify your account key and model permissions, then restart.
- **Rate limit or quota.** Check your Groq account limits and retry after reset. Requests have a timeout and a bounded retry. Long provider cooldowns are surfaced in the UI.
- **Response could not be validated.** The app requests one corrected response. Try again or use a shorter scope. Existing saved material and the resume preview remain available.
- **Local port in use.** Launch with `python -m streamlit run app.py --server.port 8502` and open the corresponding localhost port.

## Development

```sh
python -m unittest discover -s tests -v
python -m pip check
```

`app.py` handles page navigation. `ui/` contains Streamlit screens, `core/` contains ingestion, validation, Groq calls, SQLite, scheduling and export, and `prompts/templates.py` holds versioned prompts. Tests use synthetic inputs, a temporary database and mocked Groq responses.

The reference APIs are documented by [Streamlit](https://docs.streamlit.io/develop/api-reference/execution-flow/st.form), [pypdf](https://pypdf.readthedocs.io/en/stable/user/extract-text.html), [Pydantic](https://docs.pydantic.dev/latest/concepts/models/), and the [Groq Python SDK](https://github.com/groq/groq-python). Dependencies retain their own licenses. Original application code is available under the [MIT License](LICENSE).

## Phase 2 implementation status

The Knowledge Library currently supports explicit public webpage imports using Trafilatura,
text/Markdown/PDF uploads, and pasted text. Sources are shared across preparation profiles.
Imports use a repeatable additive schema, content hashes and historical versions. Search uses
SQLite FTS5, with word-frequency lexical matching when FTS5 is unavailable. Each retrieval
includes up to four passages from distinct sources. Failed refreshes preserve searchable text.
Deleting a source removes its versions and index entries while saved lessons retain their evidence.

Lessons and feedback receive bounded passages. Structured citation identifiers and exact quotations
are validated before saving. Evidence snapshots accompany lessons and Markdown exports.
Citation checks establish passage identity only. General-knowledge answers and partial support are
labelled. Source changes affect retrieval cache keys. No search credentials are needed.

Install the updated requirements and restart Streamlit. Trafilatura 2.3.1 was installed for this
increment. Downloads are capped at 2 MB, PDFs at 30 pages, extracted sources at 100,000 characters,
and the library at 100 sources / five million characters including retained versions.
HTTP connections use a validated pinned public IP and HTTPS hostname verification. Each redirect
is validated. Paste or upload a permitted copy if a site blocks retrieval.

This is an incomplete Phase 2 increment. GitHub folder selection, automated discovery, company
report extraction and historical coverage, configurable library limits, explicit source selection
per lesson, richer metadata extraction, and full Phase 2 browser/live verification remain pending.
Existing Phase 1 tests and three library tests pass (22 total). Live cited model generation has
not been verified. Network imports require internet access. Saved material and local search work
offline. Model generation requires the configured Groq key and available provider quota.

## Phase 3 interview room

Open **Interview Room** after selecting a preparation profile. Choose one of six modes, a
topic/project, difficulty, a question budget of 1–10, and coach or simulation mode. Company and
role come from the editable preparation profile. English is the configured interview language.

Questions are generated explicitly on start. Each answer may be recorded, uploaded as a 16-bit
PCM WAV, or typed. Microphone recording uses Streamlit's 16 kHz audio input. Allow microphone
access to localhost in the browser. If permission is denied or no device is available, use typing.
Use **Transcribe recording**, edit the transcript, then **Confirm answer**. Evaluation is a separate
action, so failed evaluation can be retried without repeating transcription. The original transcript
and corrected answer remain distinct. Discard a recording before submission if needed.

Set these optional environment variables or Streamlit secrets before launch.

```toml
GROQ_STT_MODEL = "whisper-large-v3-turbo"
CRACKMATE_AUDIO_MB = 10
CRACKMATE_AUDIO_SECONDS = 180
```

The application accepts PCM WAV only to validate duration and detect empty, truncated or silent
recordings locally. The configurable maximums are 24 MB and 600 seconds. Groq documents a 25 MB
free-tier upload limit. Provider availability and quotas depend on the account. No billing is
enabled by the application. [Groq speech documentation](https://console.groq.com/docs/speech-to-text)

Spoken questions use an embedded browser speech-synthesis component with play/replay, stop,
English voice selection and speed. Playback requires a click. Stop speech before starting a
recording. Browser voices and microphone hardware vary. Unsupported browsers retain text questions.

Session snapshots are saved transactionally in the existing SQLite database. Reload the page and
select a saved session to resume. Pausing retains confirmed answers. Raw recordings live only in
Streamlit session memory, remain available after a transcription error, and are cleared from the
application session on confirmation, discard, pause, end or deletion. A full browser refresh may
require recording again. Streamlit controls its underlying upload-buffer garbage collection.
No persistent audio is offered. Deleting a preparation profile cascades to its interviews. Local
deletion does not delete provider-retained data.

Coach mode shows feedback and permits retries. Simulation mode defers feedback until completion.
Revealing feedback early switches to coach mode. A follow-up replaces the next planned question,
counts toward the question budget and has a maximum depth of one. Skips are recorded without
scores. Reports calculate separate technical and behavioural averages from the latest successful
answer per question and preserve prior retry feedback. Scores are coaching estimates. DSA code
is reviewed as text and never executed.

Run the updated app with the same commands.

```sh
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
python -m unittest discover -s tests
```

With no model key, existing sessions and reports remain readable. New plans and evaluations
require Groq. With no internet or exhausted quotas, completed work remains local and typed
answers can be confirmed for later evaluation.

### Verification limits and manual device checks

Automated tests mock hosted services and cover corrected transcript scoring, duplicate evaluation,
session recovery, follow-up counting, skipped-score denominators, profile deletion, malformed and
silent WAV, transient transcription retries and simulation feedback hiding. Live hosted transcription
and evaluation require credentials and have not been verified. Microphone capture and audible
playback require a user/device check.

To verify a device, open localhost in Chrome, start an interview with spoken questions enabled,
choose an English voice, play and stop the question, record a short answer, then transcribe it.
Correct a technical term, confirm the transcript and evaluate. Refresh and confirm the saved
session recovers. Repeat in simulation mode and check feedback appears only after ending the
session or explicitly switching to coach mode. Deny microphone permission and verify typing works.
