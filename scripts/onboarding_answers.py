"""Turn the body of an "Onboard an app" issue into the answers both templates
read (Copier --data-file).

GitHub renders an issue form as Markdown: "### <Label>" followed by the value,
checkboxes as "- [x] Option". Usage:
    python scripts/onboarding_answers.py <issue-body.md> [--repos <dir>] > answers.json
Prints the answers for the whole app (the GitOps render). With --repos, also
writes one answers file per app repository into <dir> (the app-repo renders:
<dir>/app.json for an app in one repository, <dir>/backend.json and
<dir>/frontend.json for an app split in one repository per component) and
<dir>/repos.json listing them. Exits 1 with a readable message when a value is
invalid, so the workflow can post it back on the issue.
"""
import json
import os
import re
import sys

NAME = re.compile(r"^[a-z][a-z0-9-]{0,30}$")
REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")

# Form label -> answer key (labels as in .github/ISSUE_TEMPLATE/onboard-app.yml)
FIELDS = {
    "App name": "app",
    "GitHub repository": "repository",
    "Backend repository": "backend_repository",
    "Frontend repository": "frontend_repository",
    "Backend": "backend",
    "Backend port": "backend_port",
    "Backend database layer": "backend_orm",
    "Frontend": "frontend",
    "Background worker (name)": "worker",
    "Worker command": "worker_command",
    "Package manager": "package_manager",
    "The app needs": "needs",
    "Owner": "owner",
}


def sections(body: str) -> dict:
    out, key = {}, None
    for line in body.splitlines():
        if line.startswith("### "):
            key = line[4:].strip()
            out[key] = []
        elif key is not None:
            out[key].append(line)
    return {k: "\n".join(v).strip() for k, v in out.items()}


def fail(msg: str):
    print(f"invalid form: {msg}", file=sys.stderr)
    sys.exit(1)


def parse(body: str) -> dict:
    raw = {FIELDS[k]: v for k, v in sections(body).items() if k in FIELDS}
    empty = {"", "_No response_", "None"}

    def get(k, d=""):
        v = (raw.get(k) or "").strip()
        return d if v in empty else v

    app = get("app")
    if not NAME.match(app):
        fail(f"app name '{app}' must be lowercase letters, digits and '-'")
    backend = get("backend", "nestjs")
    frontend = get("frontend", "nextjs")
    if backend == "not-needed" and frontend == "not-needed":
        fail("an app needs at least a backend or a frontend")

    # One repository for the whole app (folders backend/, frontend/), or one per
    # component (the code at each repository's root). Not both, not neither.
    repository = get("repository")
    backend_repo = get("backend_repository")
    frontend_repo = get("frontend_repository")
    for label, value in (("repository", repository), ("backend repository", backend_repo),
                         ("frontend repository", frontend_repo)):
        if value and not REPO.match(value):
            fail(f"{label} '{value}' must be owner/name")
    if repository and (backend_repo or frontend_repo):
        fail("give either one repository for the whole app, or one per component, not both")
    if not repository and not (backend_repo or frontend_repo):
        fail("a repository is needed: one for the whole app, or one per component")
    if backend_repo and backend == "not-needed":
        fail("a backend repository was given, but the backend is not-needed")
    if frontend_repo and frontend == "not-needed":
        fail("a frontend repository was given, but the frontend is not-needed")
    if not repository:
        if backend != "not-needed" and not backend_repo:
            fail("the backend has no repository: fill 'Backend repository' (or the whole-app repository)")
        if frontend != "not-needed" and not frontend_repo:
            fail("the frontend has no repository: fill 'Frontend repository' (or the whole-app repository)")
        if backend_repo and backend_repo == frontend_repo:
            fail("backend and frontend repositories are the same: use the whole-app repository field")
    layout = "folders" if repository else "root"

    worker = get("worker")
    if worker and not NAME.match(worker):
        fail(f"worker name '{worker}' must be lowercase letters, digits and '-'")
    if worker and backend == "not-needed":
        fail("a worker runs the backend image, so it needs a backend")
    port = get("backend_port", "3001")
    if not port.isdigit() or not 1 <= int(port) <= 65535:
        fail(f"backend port '{port}' is not a port number")
    needs = raw.get("needs", "")

    return {
        "app": app,
        # The GitOps folder records the first repository; the split ones are below.
        "repository": repository or backend_repo or frontend_repo,
        "layout": layout,
        "backend_repository": backend_repo,
        "frontend_repository": frontend_repo,
        "backend": backend,
        "backend_port": int(port),
        "backend_orm": get("backend_orm", "prisma"),
        "frontend": frontend,
        "worker": worker,
        "worker_command": get("worker_command", "node dist/worker.js") or "node dist/worker.js",
        "package_manager": get("package_manager", "npm"),
        "needs_postgres": "[x] PostgreSQL" in needs,
        "needs_redis": "[x] Redis" in needs,
        "needs_kafka": "[x] Kafka" in needs,
        "owner": get("owner"),
    }


def repo_renders(answers: dict) -> list:
    """One app-repo render per repository: (name, answers for that repository)."""
    if answers["layout"] == "folders":
        return [("app", dict(answers))]
    renders = []
    if answers["backend"] != "not-needed":
        a = dict(answers, repository=answers["backend_repository"], frontend="not-needed")
        renders.append(("backend", a))
    if answers["frontend"] != "not-needed":
        # A frontend repository builds a frontend image only: no backend fields, no
        # worker, and none of the backend's service needs in its catalog entry.
        a = dict(answers, repository=answers["frontend_repository"], backend="not-needed",
                 worker="", needs_postgres=False, needs_redis=False, needs_kafka=False)
        renders.append(("frontend", a))
    return renders


def main(argv: list):
    path = argv[0]
    repos_dir = argv[argv.index("--repos") + 1] if "--repos" in argv else None
    body = open(path, encoding="utf-8").read()
    answers = parse(body)
    if repos_dir:
        os.makedirs(repos_dir, exist_ok=True)
        listing = []
        for name, a in repo_renders(answers):
            with open(os.path.join(repos_dir, f"{name}.json"), "w", encoding="utf-8") as fh:
                json.dump(a, fh, indent=2)
            components = [c for c in ("backend", "frontend") if a[c] != "not-needed"]
            listing.append({"name": name, "repository": a["repository"], "layout": a["layout"],
                            "components": components})
        with open(os.path.join(repos_dir, "repos.json"), "w", encoding="utf-8") as fh:
            json.dump(listing, fh, indent=2)
    # YAML-compatible JSON: Copier reads it as a data file.
    print(json.dumps(answers, indent=2))


if __name__ == "__main__":
    main(sys.argv[1:])
