"""Projects API routes."""
from uuid import UUID

from flask import Blueprint, request, jsonify

from app.db.store import project_store
from app.models.project import ProjectPhase
from app.schemas.project import ProjectCreate, ProjectUpdate

projects_bp = Blueprint("projects", __name__)


def _to_response(project):
    return {
        "id": str(project.id),
        "name": project.name,
        "domain_url": project.domain_url,
        "phase": project.phase.value,
        "qa_score": project.qa_score,
        "last_run": project.last_run.isoformat(),
    }


PILLAR_SLUGS = [
    "responsiveness",
    "ada-accessibility",
    "functional",
    "page-speed",
    "seo",
    "security",
]

# Mock issues per pillar type (keyed by slug)
def _mock_issues(slug, failed_count, project_name):
    templates = {
        "responsiveness": [
            ("Product grid breaks on mobile", "Product cards overflow and overlap on screens below 480px.", "/products", "Switch to single column layout on mobile."),
            ("Checkout form unusable on tablet", "Payment form fields are cut off on iPad landscape.", "/checkout", "Redesign checkout layout for tablet breakpoints."),
            ("Hero image too large on mobile", "Above-the-fold image causes excessive scrolling on small devices.", "/", "Use responsive image with smaller mobile asset."),
        ],
        "ada-accessibility": [
            ("Images missing alt text", "Product thumbnails have empty or missing alt attributes.", "/products", "Add descriptive alt text to all product images."),
            ("Form labels not associated", "Checkout fields lack proper label associations.", "/checkout", "Use for/id or aria-label on all form inputs."),
            ("Color contrast too low", "Body text fails WCAG AA on secondary backgrounds.", "/", "Increase contrast ratio to at least 4.5:1."),
        ],
        "functional": [
            ("Search returns 500 on special chars", "Query with quotes or ampersand triggers server error.", "/search", "Escape user input and handle errors gracefully."),
            ("Add to cart fails in Safari", "Button click does nothing on iOS Safari.", "/products", "Test and fix event handling for WebKit."),
        ],
        "page-speed": [
            ("LCP above 2.5s on homepage", "Largest contentful paint exceeds recommended threshold.", "/", "Optimize hero image and defer non-critical JS."),
            ("CLS from dynamic ads", "Cumulative layout shift from ad slot resizing.", "/", "Reserve space for ad slots or use stable placeholders."),
        ],
        "seo": [
            ("Missing meta description", "Key pages have no meta description tag.", "/products", "Add unique meta descriptions (150–160 chars)."),
            ("H1 missing on category pages", "Category pages lack a single H1 heading.", "/categories", "Add one H1 per page reflecting the category."),
        ],
        "security": [
            ("Cookie without Secure flag", "Session cookie sent over non-HTTPS.", "/", "Set Secure and SameSite on all cookies."),
            ("Mixed content on checkout", "Payment page loads script over HTTP.", "/checkout", "Load all assets over HTTPS."),
        ],
    }
    issues_list = templates.get(slug, [
        ("Sample issue", "Description for this pillar.", "/page", "Recommendation here."),
    ])
    issues = []
    for i, (title, desc, page, rec) in enumerate(issues_list[: max(1, min(3, failed_count + 1))]):
        issues.append({
            "title": title,
            "severity": "critical" if i == 0 else "warning",
            "status": "open",
            "description": desc,
            "page": page,
            "recommendation": rec,
        })
    return issues


def _pillars_for_project(project):
    """Return mock QA pillar data derived from overall score (for detail page)."""
    base = project.qa_score
    last_run = project.last_run.isoformat()
    sid = str(project.id)
    names = [
        ("Responsiveness", 0),
        ("ADA / Accessibility", -2),
        ("Functional", 1),
        ("Page Speed / CWV", -1),
        ("SEO", 0),
        ("Security", 2),
    ]
    pillars = []
    for i, (name, delta) in enumerate(names):
        seed = sum(ord(c) for c in (sid + name)[:20])
        score = max(0, min(100, base + delta + (seed % 5) - 2))
        passed = (score * 3) // 5 + (seed % 10)
        failed = max(0, (100 - score) // 10)
        warning = max(0, (100 - score) // 20)
        total = passed + failed + warning
        slug = PILLAR_SLUGS[i] if i < len(PILLAR_SLUGS) else "pillar-" + str(i)
        pillars.append({
            "name": name,
            "slug": slug,
            "score": score,
            "passed": passed,
            "failed": failed,
            "warning": warning,
            "total": total,
            "last_run": last_run,
            "issues": _mock_issues(slug, failed, project.name),
        })
    return pillars


@projects_bp.route("", methods=["GET"])
def list_projects():
    """List all projects, optionally filtered by phase."""
    phase_arg = request.args.get("phase")
    phase = ProjectPhase(phase_arg) if phase_arg in {p.value for p in ProjectPhase} else None
    projects = project_store.list_all(phase=phase)
    return jsonify([_to_response(p) for p in projects])


@projects_bp.route("/<project_id>", methods=["GET"])
def get_project(project_id):
    """Get a single project by id (includes QA pillars for detail page)."""
    try:
        uid = UUID(project_id)
    except ValueError:
        return jsonify({"detail": "Invalid project id"}), 400
    project = project_store.get(uid)
    if not project:
        return jsonify({"detail": "Project not found"}), 404
    data = _to_response(project)
    data["pillars"] = _pillars_for_project(project)
    return jsonify(data)


@projects_bp.route("/<project_id>/pillars/<pillar_slug>", methods=["GET"])
def get_project_pillar(project_id, pillar_slug):
    """Get a single pillar for a project (for pillar detail page)."""
    try:
        uid = UUID(project_id)
    except ValueError:
        return jsonify({"detail": "Invalid project id"}), 400
    project = project_store.get(uid)
    if not project:
        return jsonify({"detail": "Project not found"}), 404
    pillars = _pillars_for_project(project)
    pillar = next((p for p in pillars if p.get("slug") == pillar_slug), None)
    if not pillar:
        return jsonify({"detail": "Pillar not found"}), 404
    data = _to_response(project)
    data["pillar"] = pillar
    return jsonify(data)


@projects_bp.route("", methods=["POST"])
def create_project():
    """Create a new project."""
    data = request.get_json()
    if not data:
        return jsonify({"detail": "JSON body required"}), 400
    try:
        payload = ProjectCreate.model_validate(data)
    except Exception as e:
        return jsonify({"detail": str(e)}), 422
    project = project_store.create(
        name=payload.name,
        domain_url=payload.domain_url,
        phase=payload.phase,
    )
    return jsonify(_to_response(project)), 201


@projects_bp.route("/<project_id>", methods=["PATCH"])
def update_project(project_id):
    """Update a project (partial)."""
    try:
        uid = UUID(project_id)
    except ValueError:
        return jsonify({"detail": "Invalid project id"}), 400
    project = project_store.get(uid)
    if not project:
        return jsonify({"detail": "Project not found"}), 404
    data = request.get_json()
    if not data:
        return jsonify({"detail": "JSON body required"}), 400
    try:
        payload = ProjectUpdate.model_validate(data)
    except Exception as e:
        return jsonify({"detail": str(e)}), 422
    update_data = payload.model_dump(exclude_unset=True)
    if "phase" in update_data and isinstance(update_data["phase"], str):
        update_data["phase"] = ProjectPhase(update_data["phase"])
    updated = project_store.update(uid, **update_data)
    return jsonify(_to_response(updated))


@projects_bp.route("/<project_id>", methods=["DELETE"])
def delete_project(project_id):
    """Delete a project."""
    try:
        uid = UUID(project_id)
    except ValueError:
        return jsonify({"detail": "Invalid project id"}), 400
    if not project_store.delete(uid):
        return jsonify({"detail": "Project not found"}), 404
    return "", 204
