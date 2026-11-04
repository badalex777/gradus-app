# Gradus

**A research and data-management tool for international university advising.**

Gradus is a work in progress for organizing university research used in college counseling. Its goal is to turn research documents into structured, comparable information about universities, programs, admissions requirements, costs, and pathway options—then help advisors evaluate pathway eligibility consistently.

The project is designed around the needs of students in Latin America exploring study options abroad. It currently consists of backend data and processing tools; it is **not yet a finished web application**.

## Project status

This repository is an early-stage prototype and portfolio project.

Some useful pieces are implemented, including Google Drive document discovery, Claude-assisted extraction, a SQLite catalog schema, and an eligibility rules engine. The React frontend and FastAPI application are currently placeholders: there is no working browser interface or API server yet.

## What it does

- **Find candidate research documents in Google Drive.** The inventory script searches file names, folder names, and searchable document content for likely university-research documents. Ambiguous candidates can be checked with an LLM.
- **Extract structured information from Google Docs.** The extraction pipeline uses Anthropic's Claude API to turn document text into structured data for student profiles, universities, programs, requirements, costs, and pathway providers. It records extraction status, token usage, and estimated cost.
- **Keep a relational catalog.** The SQLite schema covers universities, programs, admission requirements, costs, pathway providers, eligibility rules, agreements, and extraction records.
- **Evaluate pathway eligibility transparently.** The eligibility engine checks a student's nationalities and current residence against provider rules at university-specific, destination-country, and provider-wide levels. The most restrictive matching rule wins, and the result includes a per-identity explanation.
- **Initialize a local database.** The database setup script creates the schema and inserts seed pathway providers and eligibility rules.

These capabilities are currently exposed through Python modules and scripts, not through a completed web interface.

## How the workflow is intended to work

1. Connect to an authorized Google Drive account.
2. Build an inventory of candidate university research documents.
3. Review the inventory before processing documents.
4. Extract structured information from selected Google Docs with Claude.
5. Store raw extraction results in SQLite for review and later cataloging.
6. Use the catalog and eligibility rules to support advisor research.

The current extraction pipeline stores raw extraction results; a complete review, correction, and publishing workflow has not been built yet.

## Technology

- **Backend:** Python 3.11+, SQLite, FastAPI dependencies declared for future API work
- **AI extraction:** Anthropic Claude API
- **Document source:** Google Drive API with read-only OAuth access
- **Frontend foundation:** React 18, Vite, Tailwind CSS, React Router

## Repository layout

```text
backend/app/
  extraction/       Google Drive client and document extraction
  services/         Eligibility rules engine
  main.py           FastAPI entry point (not implemented yet)
  models.py         Placeholder
  schemas.py        Placeholder
  routers/          Placeholder
data/
  inventario.json   Local Drive inventory output (see privacy warning below)
scripts/
  init_db.py        Create the SQLite schema and seed rules
  inventario_drive.py
                    Discover candidate documents in Google Drive
  extract_drive.py  Run the Claude-assisted extraction pipeline
  test_eligibility.py
                    Eligibility logic checks
frontend/src/       React app structure (implementation not started)
docs/               Reserved for project documentation
```

## Getting started

### Requirements

- Python 3.11 or later
- An Anthropic API key to run document extraction
- A Google Cloud OAuth client for Google Drive access

Node.js and npm will be needed when the frontend is implemented. The current frontend directory does not yet contain an application entry point.

### Install Python dependencies

Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

On Windows PowerShell, activate it with:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install the runtime dependencies declared in `pyproject.toml`:

```bash
python -m pip install fastapi "uvicorn[standard]" sqlalchemy pydantic python-dotenv anthropic google-api-python-client google-auth-oauthlib python-docx python-multipart
```

### Initialize the local database

```bash
python scripts/init_db.py
```

This creates `data/catalogo.db` and seeds the pathway providers and eligibility rules. The database is intentionally excluded from Git.

### Configure Google Drive and Anthropic

For Google Drive access:

1. Enable the Google Drive API in a Google Cloud project.
2. Create an OAuth client for a desktop application.
3. Save its downloaded credentials file as `credentials.json` in the project root.
4. Run a Drive script locally and complete the browser authorization when prompted. The OAuth token is saved as `token.json`.

The Drive integration requests read-only access. Both `credentials.json` and `token.json` are excluded from Git.

For extraction, set `ANTHROPIC_API_KEY` in your local environment or an untracked `.env` file. Never commit API keys. Calls to the Claude API may incur charges; the extraction script displays an estimate and asks for confirmation before processing.

### Run the data scripts

After configuring Drive access:

```bash
python scripts/inventario_drive.py
```

This writes candidate document metadata to `data/inventario.json`. Review and sanitize that file before sharing or committing it.

To process the inventory with Claude:

```bash
python scripts/extract_drive.py
```

The extraction script processes Google Docs listed in the inventory, skips documents already marked successful, and records raw results in the local SQLite database.

## Privacy and public-repository warning

**Do not publish this repository's existing Git history publicly.** An earlier committed version of `data/inventario.json` contains real student-identifiable document names and Google Drive file IDs. The local inventory is now ignored and excluded from the current Git index, but that does not remove it from earlier commits. Publishing this history would still expose the data. Before publishing, either clean the history (which changes commit IDs and requires coordinating a force-push) or create a fresh public history from a sanitized snapshot. If the old history has already been made public, remove it from public history and revoke any exposed access where appropriate.

The extraction pipeline may process student information. Only use documents and services you are authorized to access, and follow the applicable privacy and data-handling requirements. Do not commit student documents, extracted records, database files, OAuth credentials, tokens, or API keys.

## Known limitations

- The FastAPI entry point, routers, database models, and API schemas are empty or incomplete.
- The React frontend has no implemented pages or API integration.
- Extraction creates raw results; automated review and promotion into the normalized catalog are not complete.
- The inventory output is tied to a real Drive account and must not be treated as safe demo data.
- The project packaging metadata may need correction before installing the repository itself as a Python package; the dependency command above installs the runtime libraries directly.

## Tests

The repository includes standalone eligibility checks:

```bash
python scripts/test_eligibility.py
python scripts/test_eligibility_full.py
```

They require the local database and its seed rules. Initialize the database first with `python scripts/init_db.py`.

## License

This project is licensed under the [MIT License](LICENSE).
