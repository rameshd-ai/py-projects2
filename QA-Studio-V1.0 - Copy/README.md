# QA Studio

**App name: QA Studio** — Website Quality Assurance Dashboard. This backend can host multiple apps; QA Studio is the first, with an **app chooser** at the root.

A dashboard to manage website QA projects: list projects, filter by phase, search, add/delete projects, and view QA scores. Built with **Python Flask** (Poetry) and **plain HTML, CSS, and JavaScript** — no React, no Node.js.

---

## Steps to run the app

### Prerequisites

- **Python 3.10+** and **Poetry** ([install Poetry](https://python-poetry.org/docs/#installation))

### Step 1: Open the project

If the folder is still named `QA-Studio-V1.0`, rename it to **QA-Studio** (e.g. in File Explorer or from a terminal when the folder is not in use). Then:

```bash
cd e:\r-git\py-projects2\QA-Studio
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

**2.3** In your browser:

- **http://localhost:8001** — app chooser (choose QA Studio or other apps).
- **http://localhost:8001/qa-studio/** — QA Studio dashboard.

The same server serves the launcher, QA Studio (HTML + API), and any future apps you add.

---

## Project structure

```
QA-Studio/
├── backend/
│   ├── app/
│   │   ├── main.py          # Flask app: launcher at /, registers app blueprints
│   │   └── config.py        # Settings
│   ├── apps/
│   │   └── qa_studio/       # QA Studio app (dashboard, project, pillar pages + API)
│   │       ├── routes.py    # Blueprint at /qa-studio
│   │       ├── static/      # index.html, project.html, pillar.html, css/, js/
│   │       ├── db/, models/, routers/, schemas/
│   │       └── ...
│   ├── static/
│   │   └── launcher.html    # App chooser page (served at /)
│   ├── run.py               # Run server: poetry run python run.py
│   ├── pyproject.toml
│   └── README.md
└── README.md
```

## API endpoints (QA Studio)

All under the `/qa-studio` prefix:

- `GET /qa-studio/api/projects` – list projects (optional `?phase=...`)
- `GET /qa-studio/api/projects/{id}` – get one project (includes pillars)
- `GET /qa-studio/api/projects/{id}/pillars/{slug}` – get pillar detail
- `POST /qa-studio/api/projects` – create project (body: `name`, `domain_url`, `phase`)
- `PATCH /qa-studio/api/projects/{id}` – update project
- `DELETE /qa-studio/api/projects/{id}` – delete project
- `GET /qa-studio/api/health` – health check

## Data

Stored locally in `backend/data/projects.json` (no database). If that file is missing, the app starts with seed projects and creates the file on first change.
