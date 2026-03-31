#!/usr/bin/env python3
"""Fetch Azure DevOps pipeline logs with structured output.

Usage:
    python3 ado_pipeline_logs.py --url "https://dev.azure.com/{org}/{project}/_build/results?buildId=123"
    python3 ado_pipeline_logs.py --org my-org --project MyProject --build-id 456
    python3 ado_pipeline_logs.py --org my-org --project MyProject --build-id 456 --failed-only
"""

import argparse
import base64
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from collections import defaultdict

# Well-known Azure AD application ID for Azure DevOps.
# Used to request an AAD token scoped to the ADO API.
# See: https://learn.microsoft.com/en-us/azure/devops/integrate/get-started/authentication/service-principal-managed-identity
ADO_RESOURCE_ID = "499b84ac-1321-427f-aa17-267ca6975798"

MAX_LOG_LINES = 5000
HEAD_LINES = 200
TAIL_LINES = 500


def get_token():
    """Get ADO access token. Tries az CLI first, falls back to ADO_PAT env var."""
    try:
        result = subprocess.run(
            ["az", "account", "get-access-token", "--resource", ADO_RESOURCE_ID],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            return json.loads(result.stdout)["accessToken"]
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError, KeyError):
        pass

    pat = os.environ.get("ADO_PAT")
    if pat:
        return pat

    print(json.dumps({
        "error": "No authentication available",
        "help": "Either run 'az login' or set the ADO_PAT environment variable"
    }))
    sys.exit(1)


def build_auth_header(token):
    """Build Basic auth header (empty username, token as password)."""
    auth_b64 = base64.b64encode(f":{token}".encode()).decode()
    return f"Basic {auth_b64}"


def fetch(url, auth_header):
    """Fetch a URL with auth. Returns parsed JSON or raw text."""
    req = urllib.request.Request(url)
    req.add_header("Authorization", auth_header)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read().decode()
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                return data  # Plain text (log content)
    except urllib.error.HTTPError as e:
        if e.code == 401:
            print(json.dumps({
                "error": f"HTTP 401 Unauthorized for {url}",
                "help": f"Token may be expired. Run: az account get-access-token --resource {ADO_RESOURCE_ID}"
            }))
            sys.exit(1)
        return {"error": f"HTTP {e.code}", "url": url}
    except urllib.error.URLError as e:
        return {"error": str(e.reason), "url": url}


def parse_url(url):
    """Extract org, project, and buildId from an ADO build URL."""
    parsed = urllib.parse.urlparse(url)
    path_parts = [p for p in parsed.path.split("/") if p]
    if len(path_parts) >= 2:
        org = path_parts[0]
        project = path_parts[1]
    else:
        return None, None, None

    params = urllib.parse.parse_qs(parsed.query)
    build_id = params.get("buildId", [None])[0]
    return org, project, build_id


def truncate_log(log_text):
    """Truncate logs over MAX_LOG_LINES, keeping head and tail."""
    if not isinstance(log_text, str):
        return log_text
    lines = log_text.splitlines()
    if len(lines) <= MAX_LOG_LINES:
        return log_text
    head = lines[:HEAD_LINES]
    tail = lines[-TAIL_LINES:]
    truncated = len(lines) - HEAD_LINES - TAIL_LINES
    return "\n".join(head + [f"\n[... {truncated} lines truncated ...]\n"] + tail)


def _make_task(task_rec):
    return {
        "name": task_rec.get("name"),
        "task_type": (task_rec.get("task") or {}).get("name"),
        "result": task_rec.get("result"),
        "state": task_rec.get("state"),
        "error_count": task_rec.get("errorCount", 0),
        "warning_count": task_rec.get("warningCount", 0),
        "issues": task_rec.get("issues", []),
        "log_id": (task_rec.get("log") or {}).get("id"),
        "log": None  # filled later
    }


def _collect_tasks(children, parent_id):
    """Recursively collect Task records under a parent (handles Phase->Job->Task)."""
    tasks = []
    for child in children.get(parent_id, []):
        if child.get("type") == "Task":
            tasks.append(_make_task(child))
        elif child.get("type") in ("Job", "Phase"):
            tasks.extend(_collect_tasks(children, child["id"]))
    return tasks


def build_hierarchy(records):
    """Build stage -> job -> task hierarchy from flat timeline records.

    ADO timelines use a 4-level hierarchy: Stage -> Phase -> Job -> Task.
    This function flattens Phase/Job into a single "jobs" level per stage.
    """
    children = defaultdict(list)
    for r in records:
        pid = r.get("parentId")
        if pid:
            children[pid].append(r)

    for pid in children:
        children[pid].sort(key=lambda r: r.get("order", 0))

    stages = []
    for r in records:
        if r.get("type") == "Stage":
            stage = {
                "name": r.get("name"),
                "result": r.get("result"),
                "state": r.get("state"),
                "jobs": []
            }
            # Collect Phase children of Stage, then Job children of Phase
            for phase_rec in children.get(r["id"], []):
                if phase_rec.get("type") != "Phase":
                    continue
                for job_rec in children.get(phase_rec["id"], []):
                    if job_rec.get("type") != "Job":
                        continue
                    job = {
                        "name": job_rec.get("name"),
                        "result": job_rec.get("result"),
                        "state": job_rec.get("state"),
                        "tasks": [
                            _make_task(t)
                            for t in children.get(job_rec["id"], [])
                            if t.get("type") == "Task"
                        ]
                    }
                    stage["jobs"].append(job)
            stages.append(stage)
    return stages


def main():
    parser = argparse.ArgumentParser(description="Fetch ADO pipeline logs")
    parser.add_argument("--url", help="Full ADO build results URL")
    parser.add_argument("--org", help="ADO organization name")
    parser.add_argument("--project", help="ADO project name")
    parser.add_argument("--build-id", help="Build ID")
    parser.add_argument("--failed-only", action="store_true",
                        help="Only fetch logs for failed tasks")
    args = parser.parse_args()

    if args.url:
        org, project, build_id = parse_url(args.url)
        if not all([org, project, build_id]):
            print(json.dumps({"error": f"Could not parse URL: {args.url}"}))
            sys.exit(1)
    elif args.org and args.project and args.build_id:
        org, project, build_id = args.org, args.project, args.build_id
    else:
        parser.error("Provide --url or all of --org, --project, --build-id")

    api_base = f"https://dev.azure.com/{org}/{project}/_apis"

    token = get_token()
    auth = build_auth_header(token)

    build = fetch(f"{api_base}/build/builds/{build_id}?api-version=7.0", auth)
    if isinstance(build, dict) and "error" in build:
        print(json.dumps(build))
        sys.exit(1)

    timeline = fetch(f"{api_base}/build/builds/{build_id}/timeline?api-version=7.0", auth)
    if isinstance(timeline, dict) and "error" in timeline:
        print(json.dumps(timeline))
        sys.exit(1)

    records = timeline.get("records", [])
    stages = build_hierarchy(records)

    tasks_to_fetch = []
    for stage in stages:
        for job in stage["jobs"]:
            for task in job["tasks"]:
                if task["log_id"] is not None:
                    if args.failed_only and task["result"] != "failed":
                        continue
                    tasks_to_fetch.append(task)

    for task in tasks_to_fetch:
        log_data = fetch(
            f"{api_base}/build/builds/{build_id}/logs/{task['log_id']}?api-version=7.0",
            auth
        )
        if isinstance(log_data, str):
            task["log"] = truncate_log(log_data)
        elif isinstance(log_data, dict) and "error" in log_data:
            task["log"] = f"[Error fetching log: {log_data['error']}]"
        else:
            task["log"] = None

    all_tasks = [t for s in stages for j in s["jobs"] for t in j["tasks"]]
    summary = {
        "total_tasks": len(all_tasks),
        "succeeded": sum(1 for t in all_tasks if t["result"] == "succeeded"),
        "failed": sum(1 for t in all_tasks if t["result"] == "failed"),
        "skipped": sum(1 for t in all_tasks if t["result"] == "skipped"),
        "other": sum(1 for t in all_tasks if t["result"] not in ("succeeded", "failed", "skipped")),
        "failed_task_names": [t["name"] for t in all_tasks if t["result"] == "failed"]
    }

    output = {
        "build_id": int(build_id),
        "build_url": f"https://dev.azure.com/{org}/{project}/_build/results?buildId={build_id}",
        "definition": (build.get("definition") or {}).get("name"),
        "result": build.get("result"),
        "status": build.get("status"),
        "source_branch": build.get("sourceBranch"),
        "start_time": build.get("startTime"),
        "finish_time": build.get("finishTime"),
        "stages": stages,
        "summary": summary
    }

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
