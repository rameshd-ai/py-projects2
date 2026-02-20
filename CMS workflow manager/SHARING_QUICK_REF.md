# Quick Reference: Sharing This Project

## What to Share with Developers

### ✅ Share These Files
```
pyproject.toml          ← Dependencies definition
poetry.lock             ← Exact versions lock file
*.py files              ← All Python source code
templates/              ← HTML templates
resource/               ← Config & mapping files
processing_steps/       ← Workflow modules
.gitignore              ← Git exclusions
SETUP_GUIDE.md          ← Setup instructions
README.md               ← Project documentation (if exists)
```

### ❌ Never Share These
```
.venv/                  ← Virtual environment
__pycache__/            ← Python cache
uploads/                ← Job data
output/                 ← Generated files
*.log                   ← Log files
.env                    ← Secrets/tokens
.vscode/, .idea/        ← IDE settings
```

---

## For New Developers

### Quick Start (3 steps)
```bash
# 1. Install Poetry (if not installed)
curl -sSL https://install.python-poetry.org | python3 -

# 2. Clone repo and install dependencies
git clone <repo-url>
cd "CMS workflow manager"
poetry install

# 3. Run the app
poetry run python app.py
```

---

## Key Points

1. **Poetry replaces pip + venv**
   - `pyproject.toml` = like `requirements.txt` but better
   - `poetry.lock` = locks exact versions for reproducibility
   - Poetry creates its own virtual environment automatically

2. **DO commit**: `pyproject.toml` + `poetry.lock` together
   - This ensures everyone gets the exact same dependencies

3. **DON'T commit**: Virtual environments or generated data
   - Already handled by `.gitignore`

4. **Adding new packages**:
   ```bash
   poetry add <package-name>
   # This updates both pyproject.toml and poetry.lock
   # Commit both files
   ```

---

## Common Developer Questions

**Q: Do I need to install venv?**  
A: No, Poetry handles virtual environments automatically.

**Q: Where is the virtual environment created?**  
A: Poetry stores it in a central cache location (not in project folder).
Check with: `poetry env info`

**Q: Can I use pip instead of Poetry?**  
A: Not recommended. But if needed, you can export:
```bash
poetry export -f requirements.txt --output requirements.txt
pip install -r requirements.txt
```

**Q: Should I commit poetry.lock?**  
A: **YES!** Always commit it. It ensures reproducible builds.

**Q: What if someone adds a package?**  
A: Pull the changes, then run:
```bash
poetry install
# This reads poetry.lock and installs new packages
```

---

See **SETUP_GUIDE.md** for detailed instructions.
