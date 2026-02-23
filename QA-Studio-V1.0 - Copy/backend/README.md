# QA Studio — Backend

Flask backend for **QA Studio** (Website Quality Assurance Dashboard). This backend belongs only to the QA Studio app.

## Setup

```bash
cd backend
poetry install
```

## Run

**Recommended** (works even when the `flask` CLI is not found):

```bash
poetry run python run.py
```

Alternative (Flask CLI):

```bash
# Windows PowerShell
$env:FLASK_APP="app.main:app"
poetry run flask run --host=0.0.0.0 --port=8001

# Linux/macOS
export FLASK_APP=app.main:app
poetry run flask run --host=0.0.0.0 --port=8001
```

API: http://localhost:8001
