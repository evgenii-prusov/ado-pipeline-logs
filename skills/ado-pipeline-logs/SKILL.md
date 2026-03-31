---
name: ado-pipeline-logs
description: Fetch and analyze Azure DevOps pipeline logs. Use when the user pastes an ADO pipeline URL, asks to "check the build", "get pipeline logs", "debug pipeline failure", "analyze build", "ADO build failed", or mentions a build ID.
argument-hint: "[build-url or --org ORG --project PROJ --build-id ID]"
---

# ADO Pipeline Logs

## Quick queries (use `az rest` directly)

For simple checks like "is the build green?" or "what failed?", use `az rest` commands from CLAUDE.md. This is faster and avoids running a script.

## Structured analysis (use the script)

For deeper debugging (multi-stage failures, root cause analysis, large pipelines), run:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/ado_pipeline_logs.py" --url "<ADO_BUILD_URL>"
```

Or with explicit args:
```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/ado_pipeline_logs.py" --org dsg-dp --project DataMesh --build-id <ID>
```

If invoked directly as `/ado-pipeline-logs <url>`, pass arguments through:
```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/ado_pipeline_logs.py" --url "$ARGUMENTS"
```

The script returns structured JSON with the full stage/job/task hierarchy and log content.

**Log content per task:**
- **Failed tasks** — full log (head + tail, truncated at 5000 lines)
- **Succeeded tasks** — last 30 lines only, plus an `error_snippet` field if error markers were detected in the log

## How to analyze the output

1. Check `summary.failed_task_names` for a quick overview
2. Look at tasks with `"result": "failed"` and read their `log` and `issues[]`
3. If the failed task log is empty or generic, check `summary.succeeded_tasks_with_errors` —
   some pipelines log errors in tasks that still report success, so the root cause may be
   in a succeeded task's `error_snippet` rather than the failed task itself

## Flags

- Default: fetches all task logs; succeeded tasks are compressed to last 30 lines + error snippets
- `--failed-only`: only fetches logs for failed tasks — fastest mode, but will miss errors
  logged in succeeded tasks

## Presenting findings

- Lead with the root cause and evidence from the log text
- Quote specific error lines from the logs
- If root cause came from a succeeded task, call this out explicitly
