"""Projects API routes."""
from urllib.parse import urlparse
from uuid import UUID

from flask import Blueprint, request, jsonify

from apps.qa_studio.db.scan_history import load_ada_scan, load_responsiveness_scan, load_content_quality_scan
from apps.qa_studio.db.store import project_store
from apps.qa_studio.models.project import ProjectPhase
from apps.qa_studio.schemas.project import ProjectCreate, ProjectUpdate

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
    "content-quality",
    "datalayer-validation",
    "functional",
    "page-speed",
    "seo",
    "security",
]


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
        "datalayer-validation": [
            ("Missing dataLayer object", "dataLayer is not defined or not pushed before GTM.", "/", "Initialize dataLayer array before GTM script loads."),
            ("Invalid event structure", "Event objects do not match schema for analytics.", "/checkout", "Ensure event, eventCategory, eventAction follow GTM naming."),
            ("Page metadata missing", "pageType or pageName not present in dataLayer.", "/", "Push page metadata on page load."),
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
    issues_list = templates.get(slug, [("Sample issue", "Description for this pillar.", "/page", "Recommendation here.")])
    issues = []
    for i, (title, desc, page, rec) in enumerate(issues_list[: max(1, min(3, failed_count + 1))]):
        issues.append({"title": title, "severity": "critical" if i == 0 else "warning", "status": "open", "description": desc, "page": page, "recommendation": rec})
    return issues


def _pillars_for_project(project):
    base = project.qa_score
    last_run = project.last_run.isoformat()
    sid = str(project.id)
    names = [
        ("Responsiveness", 0),
        ("ADA / Accessibility", -2),
        ("Content Quality", 0),
        ("Data Layer Validation", 0),
        ("Functional", 1),
        ("Page Speed / CWV", -1),
        ("SEO", 0),
        ("Security", 2),
    ]
    ada_scan = load_ada_scan(project.id)
    pillars = []
    for i, (name, delta) in enumerate(names):
        slug = PILLAR_SLUGS[i] if i < len(PILLAR_SLUGS) else "pillar-" + str(i)
        if slug == "ada-accessibility" and ada_scan:
            agg = ada_scan.get("aggregate", {})
            passed = agg.get("passed", 0) or 0
            failed = agg.get("violations", 0) or 0
            warning = agg.get("incomplete", 0) or 0
            total = passed + failed + warning
            score = max(0, min(100, round((passed / total) * 100))) if total else 0
            last_run = ada_scan.get("timestamp", last_run)
            issues = []
        else:
            score = 0
            passed = 0
            failed = 0
            warning = 0
            total = 0
            issues = []
        pillars.append({
            "name": name, "slug": slug, "score": score, "passed": passed, "failed": failed, "warning": warning,
            "total": total, "last_run": last_run, "issues": issues,
        })
    resp_scan = load_responsiveness_scan(project.id)
    cq_scan = load_content_quality_scan(project.id)
    for p in pillars:
        if p["slug"] == "ada-accessibility" and ada_scan:
            pass  # already set above
        elif p["slug"] == "responsiveness" and resp_scan:
            agg = resp_scan.get("aggregate", {})
            passed = agg.get("passed", 0) or 0
            failed = agg.get("failed", 0) or 0
            warning = agg.get("warning", 0) or 0
            total = passed + failed + warning
            score = max(0, min(100, round((passed / total) * 100))) if total else 0
            p["score"] = score
            p["passed"] = passed
            p["failed"] = failed
            p["warning"] = warning
            p["total"] = total
            p["last_run"] = resp_scan.get("timestamp", last_run)
        elif p["slug"] == "content-quality" and cq_scan:
            agg = cq_scan.get("aggregate", {})
            passed = agg.get("passed", 0) or 0
            failed = agg.get("failed", 0) or 0
            warning = agg.get("warning", 0) or 0
            total = passed + failed + warning
            score = max(0, min(100, round((passed / total) * 100))) if total else 0
            p["score"] = score
            p["passed"] = passed
            p["failed"] = failed
            p["warning"] = warning
            p["total"] = total
            p["last_run"] = cq_scan.get("timestamp", last_run)
        p["enabled"] = p["slug"] in ("ada-accessibility", "responsiveness", "content-quality")
    return pillars


@projects_bp.route("", methods=["GET"])
def list_projects():
    phase_arg = request.args.get("phase")
    phase = ProjectPhase(phase_arg) if phase_arg in {p.value for p in ProjectPhase} else None
    projects = project_store.list_all(phase=phase)
    return jsonify([_to_response(p) for p in projects])


@projects_bp.route("/<project_id>", methods=["GET"])
def get_project(project_id):
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


def _name_from_url(url: str) -> str:
    """Derive project name from domain URL (e.g. https://example.com -> example.com)."""
    try:
        parsed = urlparse(url)
        host = parsed.netloc or parsed.path or url
        return host.split(":")[0].lstrip("www.") or url
    except Exception:
        return url


@projects_bp.route("", methods=["POST"])
def create_project():
    data = request.get_json()
    if not data:
        return jsonify({"detail": "JSON body required"}), 400
    try:
        payload = ProjectCreate.model_validate(data)
    except Exception as e:
        return jsonify({"detail": str(e)}), 422
    domain_url = (payload.domain_url or "").strip()
    if not domain_url:
        return jsonify({"detail": "domain_url is required"}), 422
    name = (payload.name or "").strip() or _name_from_url(domain_url)
    project = project_store.create(name=name, domain_url=domain_url, phase=payload.phase)
    return jsonify(_to_response(project)), 201


@projects_bp.route("/<project_id>", methods=["PATCH"])
def update_project(project_id):
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
    try:
        uid = UUID(project_id)
    except ValueError:
        return jsonify({"detail": "Invalid project id"}), 400
    if not project_store.delete(uid):
        return jsonify({"detail": "Project not found"}), 404
    return "", 204
