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

## How to analyze the output

1. Check `summary.failed_task_names` for a quick overview
2. Look at tasks with `"result": "failed"` first
3. Check `issues[]` on failed tasks for inline error messages
4. Read the `log` field for full log content (truncated if >5000 lines)
5. Check successful tasks before the failure for context (e.g., which files were processed before the error)

## Presenting findings

- Lead with the root cause and evidence from the log text
- Quote specific error lines from the logs
- If the error matches a known pattern (see CLAUDE.md error table), include the fix
- For Snowflake deployment errors, check if the user/role exists and suggest YAML or ownership changes
