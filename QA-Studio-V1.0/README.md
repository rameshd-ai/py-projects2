# QA Studio – Website Quality Assurance Dashboard

A dashboard to manage website QA projects: list projects, filter by phase, search, add/delete projects, and view QA scores. Built with **Python Flask** (Poetry) and **plain HTML, CSS, and JavaScript** — no React, no Node.js.

---

## Steps to run the app

### Prerequisites

- **Python 3.10+** and **Poetry** ([install Poetry](https://python-poetry.org/docs/#installation))

### Step 1: Open the project

```bash
cd e:\r-git\py-projects2\QA-Studio-V1.0
```

### Step 2: Install and start (one server does everything)

**2.1** Go to the backend folder and install dependencies (required — otherwise you’ll get `No module named 'flask'`):

```bash
cd backend
poetry install
```

**2.2** Start the server:

```bash
poetry run python run.py
```

**2.3** Open the dashboard in your browser at **http://localhost:8001**.

That’s it. The same server serves both the API and the HTML dashboard.

---

## Project structure

```
QA-Studio-V1.0/
├── backend/
│   ├── app/
│   │   ├── main.py          # Flask app, routes, serves dashboard
│   │   ├── config.py        # Settings
│   │   ├── db/              # Local file storage
│   │   ├── models/          # Domain models
│   │   ├── routers/         # API routes (projects)
│   │   └── schemas/         # Pydantic request validation
│   ├── static/              # Dashboard (HTML, CSS, JS)
│   │   ├── index.html
│   │   ├── css/style.css
│   │   └── js/app.js
│   ├── run.py               # Run server: poetry run python run.py
│   ├── pyproject.toml
│   └── README.md
└── README.md
```

## API endpoints

- `GET /api/projects` – list projects (optional `?phase=Live` or `Test Link` or `Development`)
- `GET /api/projects/{id}` – get one project
- `POST /api/projects` – create project (body: `name`, `domain_url`, `phase`)
- `PATCH /api/projects/{id}` – update project
- `DELETE /api/projects/{id}` – delete project

## Data

Stored locally in `backend/data/projects.json` (no database). If that file is missing, the app starts with seed projects and creates the file on first change.
