import os
import re
import json
from datetime import datetime
from urllib.parse import urlparse

import requests
from flask import Flask, render_template, request, jsonify, send_from_directory

app = Flask(__name__)

OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

GITHUB_API_BASE = "https://api.github.com"


def parse_github_repo_url(repo_url: str):
    if not repo_url:
        raise ValueError("Repository URL is required.")

    repo_url = repo_url.strip()
    parsed = urlparse(repo_url)

    if "github.com" not in parsed.netloc.lower():
        raise ValueError("Please enter a valid GitHub repository URL.")

    parts = [p for p in parsed.path.strip("/").split("/") if p]

    if len(parts) < 2:
        raise ValueError("Repository URL must look like https://github.com/owner/repo")

    owner = parts[0]
    repo = parts[1].replace(".git", "")
    return owner, repo


def github_get(url, raw=False):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "repo-readiness-checker"
    }

    if raw:
        headers["Accept"] = "application/vnd.github.raw+json"

    response = requests.get(url, headers=headers, timeout=20)
    return response


def repo_exists(owner, repo):
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}"
    response = github_get(url)
    return response.status_code == 200, response.json() if response.status_code == 200 else None


def get_repo_root_contents(owner, repo):
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents"
    response = github_get(url)
    if response.status_code != 200:
      return []
    return response.json()


def get_readme(owner, repo):
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/readme"
    response = github_get(url, raw=True)
    if response.status_code == 200:
        return response.text
    return ""


def get_workflows(owner, repo):
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/.github/workflows"
    response = github_get(url)
    if response.status_code == 200:
        return response.json()
    return []


def get_gitlab_ci_like(owner, repo):
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/.gitlab-ci.yml"
    response = github_get(url)
    return response.status_code == 200


def get_releases(owner, repo):
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/releases"
    response = github_get(url)
    if response.status_code == 200:
        return response.json()
    return []


def get_tags(owner, repo):
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/tags"
    response = github_get(url)
    if response.status_code == 200:
        return response.json()
    return []


def find_file_in_root(contents, possible_names):
    names = {item.get("name", "").lower(): item for item in contents if isinstance(item, dict)}
    for filename in possible_names:
        if filename.lower() in names:
            return True, names[filename.lower()]
    return False, None


def has_tests(contents):
    test_indicators = {
        "tests", "test", "pytest.ini", "tox.ini", "noxfile.py",
        "package.json", "unittest", "conftest.py"
    }

    names = set(item.get("name", "").lower() for item in contents if isinstance(item, dict))
    if names.intersection(test_indicators):
        return True

    for item in contents:
        if isinstance(item, dict):
            name = item.get("name", "").lower()
            if "test" in name:
                return True

    return False


def infer_test_command(contents):
    names = set(item.get("name", "").lower() for item in contents if isinstance(item, dict))

    if "pytest.ini" in names or "conftest.py" in names or "tests" in names:
        return "pytest"
    if "package.json" in names:
        return "npm test"
    if "test" in names:
        return "python -m unittest"
    return "Not verified in web mode"


def check_readme_quality(readme_text):
    if not readme_text.strip():
        return 0, "fail", "README not found."

    lower = readme_text.lower()
    install_words = ["install", "installation", "setup", "requirements"]
    run_words = ["usage", "run", "quickstart", "getting started", "how to run", "example"]

    has_install = any(word in lower for word in install_words)
    has_run = any(word in lower for word in run_words)

    if has_install and has_run:
        return 20, "pass", "README includes install/setup and run/usage guidance."
    if has_install or has_run:
        return 10, "partial", "README exists, but install or run instructions are incomplete."
    return 5, "partial", "README exists, but clear install/run instructions were not detected."


def check_license(contents):
    found, _ = find_file_in_root(contents, ["LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING"])
    if found:
        return 15, "pass", "License file is present."
    return 0, "fail", "License file is missing."


def check_tests(contents):
    if has_tests(contents):
        cmd = infer_test_command(contents)
        return 15, "pass", f"Test-related files detected. Suggested command: {cmd}."
    return 0, "fail", "No clear test files or test folders detected."


def check_test_command(contents):
    if has_tests(contents):
        cmd = infer_test_command(contents)
        return 10, "partial", f"Test command inferred as '{cmd}', but execution is not performed in this web-only version."
    return 0, "fail", "Test command could not be inferred because tests were not detected."


def check_ci(owner, repo):
    workflows = get_workflows(owner, repo)
    gitlab_ci = get_gitlab_ci_like(owner, repo)

    if workflows or gitlab_ci:
        return 10, "pass", "CI configuration detected."
    return 0, "fail", "No GitHub Actions or GitLab CI configuration found."


def check_versioning(owner, repo):
    releases = get_releases(owner, repo)
    tags = get_tags(owner, repo)

    if releases:
        return 10, "pass", "Release history is present."
    if tags:
        return 7, "partial", "Git tags exist, but no formal GitHub releases were detected."
    return 0, "fail", "No release tags or version history detected."


def check_citation(contents, readme_text):
    found, _ = find_file_in_root(contents, ["CITATION.cff", "CITATION", "citation.cff"])
    if found:
        return 10, "pass", "Citation file is present."

    lower = readme_text.lower()
    if "citation" in lower or "how to cite" in lower or "references" in lower:
        return 6, "partial", "README appears to contain citation/reference information."
    return 0, "fail", "No citation file or clear citation/reference section detected."


def prioritize_fixes(checks):
    priority_order = [
        "README Quality",
        "License",
        "Tests Present",
        "Test Command",
        "CI Configuration",
        "Versioning/Releases",
        "Citation Support"
    ]

    fix_map = {
        "README Quality": "Add clear README sections for installation, setup, and usage/run instructions.",
        "License": "Add a LICENSE file so reuse terms are explicit.",
        "Tests Present": "Add a tests folder or test configuration such as pytest/unittest.",
        "Test Command": "Document and validate a working test command such as pytest or npm test.",
        "CI Configuration": "Add GitHub Actions or GitLab CI to run tests automatically.",
        "Versioning/Releases": "Create version tags and at least one formal release.",
        "Citation Support": "Add a CITATION.cff file or a clear citation section in the README."
    }

    checklist = []
    check_lookup = {c["name"]: c for c in checks}

    for name in priority_order:
        c = check_lookup.get(name)
        if c and c["status"] != "pass":
            checklist.append(fix_map[name])

    return checklist


def generate_html_report(report):
    rows = ""
    for check in report["checks"]:
        rows += f"""
        <tr>
          <td>{check['name']}</td>
          <td>{check['status']}</td>
          <td>{check['score']} / {check['weight']}</td>
          <td>{check['rationale']}</td>
        </tr>
        """

    fix_items = "".join(f"<li>{item}</li>" for item in report["fix_checklist"])

    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1.0" />
      <title>Repo Readiness Report</title>
      <style>
        body {{
          font-family: Arial, sans-serif;
          margin: 40px;
          background: #f8fafc;
          color: #111827;
        }}
        .wrap {{
          max-width: 1000px;
          margin: auto;
          background: white;
          border: 1px solid #e5e7eb;
          border-radius: 16px;
          padding: 24px;
        }}
        h1, h2, h3 {{
          margin-top: 0;
        }}
        .score {{
          font-size: 32px;
          font-weight: bold;
          color: #0f766e;
          margin-bottom: 16px;
        }}
        table {{
          width: 100%;
          border-collapse: collapse;
          margin-top: 12px;
        }}
        th, td {{
          border: 1px solid #e5e7eb;
          padding: 10px;
          text-align: left;
          vertical-align: top;
        }}
        th {{
          background: #f1f5f9;
        }}
      </style>
    </head>
    <body>
      <div class="wrap">
        <h1>Research Software Readiness Report</h1>
        <p><strong>Repository:</strong> {report['repo']}</p>
        <p><strong>URL:</strong> {report['repo_url']}</p>
        <div class="score">Score: {report['total_score']} / 100</div>

        <h2>Checks</h2>
        <table>
          <thead>
            <tr>
              <th>Check</th>
              <th>Status</th>
              <th>Score</th>
              <th>Rationale</th>
            </tr>
          </thead>
          <tbody>
            {rows}
          </tbody>
        </table>

        <h2 style="margin-top: 24px;">Prioritized Fix Checklist</h2>
        <ul>
          {fix_items if fix_items else '<li>No major fixes suggested.</li>'}
        </ul>
      </div>
    </body>
    </html>
    """
    return html


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json(silent=True) or {}
    repo_url = (data.get("repo_url") or "").strip()

    if not repo_url:
        return jsonify({"error": "Repository URL is required."}), 400

    try:
        owner, repo = parse_github_repo_url(repo_url)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    exists, repo_meta = repo_exists(owner, repo)
    if not exists:
        return jsonify({"error": "Repository not found or not publicly accessible."}), 404

    contents = get_repo_root_contents(owner, repo)
    readme_text = get_readme(owner, repo)

    checks = []

    score, status, rationale = check_readme_quality(readme_text)
    checks.append({
        "name": "README Quality",
        "status": status,
        "score": score,
        "weight": 20,
        "rationale": rationale
    })

    score, status, rationale = check_license(contents)
    checks.append({
        "name": "License",
        "status": status,
        "score": score,
        "weight": 15,
        "rationale": rationale
    })

    score, status, rationale = check_tests(contents)
    checks.append({
        "name": "Tests Present",
        "status": status,
        "score": score,
        "weight": 15,
        "rationale": rationale
    })

    score, status, rationale = check_test_command(contents)
    checks.append({
        "name": "Test Command",
        "status": status,
        "score": score,
        "weight": 20,
        "rationale": rationale
    })

    score, status, rationale = check_ci(owner, repo)
    checks.append({
        "name": "CI Configuration",
        "status": status,
        "score": score,
        "weight": 10,
        "rationale": rationale
    })

    score, status, rationale = check_versioning(owner, repo)
    checks.append({
        "name": "Versioning/Releases",
        "status": status,
        "score": score,
        "weight": 10,
        "rationale": rationale
    })

    score, status, rationale = check_citation(contents, readme_text)
    checks.append({
        "name": "Citation Support",
        "status": status,
        "score": score,
        "weight": 10,
        "rationale": rationale
    })

    total_score = sum(item["score"] for item in checks)
    total_score = min(total_score, 100)

    report = {
        "repo": f"{owner}/{repo}",
        "repo_url": repo_url,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "default_branch": repo_meta.get("default_branch"),
        "description": repo_meta.get("description"),
        "total_score": total_score,
        "checks": checks,
        "fix_checklist": prioritize_fixes(checks)
    }

    safe_repo_name = re.sub(r"[^a-zA-Z0-9_.-]", "_", f"{owner}_{repo}")
    json_filename = f"{safe_repo_name}_report.json"
    html_filename = f"{safe_repo_name}_report.html"

    json_path = os.path.join(OUTPUT_DIR, json_filename)
    html_path = os.path.join(OUTPUT_DIR, html_filename)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    html_report = generate_html_report(report)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_report)

    report["json_download_url"] = f"/download/{json_filename}"
    report["html_download_url"] = f"/download/{html_filename}"

    return jsonify(report)


@app.route("/download/<path:filename>")
def download_file(filename):
    return send_from_directory(OUTPUT_DIR, filename, as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True)