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
2. Check `summary.succeeded_tasks_with_errors` — **this is critical**. Some pipelines use a
   "collect errors, fail at the end" pattern where the failed task only says "X files not
   processed" but the actual stack trace is in a preceding succeeded task's log. If the
   failed task log contains no diagnostics, the root cause is here.
3. Look at tasks with `"result": "failed"` and read their `log` and `issues[]`
4. If the failed task log is empty or generic, read the `error_snippet` on the succeeded
   tasks listed in `summary.succeeded_tasks_with_errors`

### Known pattern: error buried in a succeeded task

Symptom: failed task log only says something like "The following files have not been
processed due to errors: [list]" with no stack trace.

Action: look at `summary.succeeded_tasks_with_errors` — the actual exception (e.g.
`TypeError`, `ProgrammingError`) will be in the `error_snippet` of a task like
"Dry run on non-execution mode" that ran earlier and swallowed its errors.

## Flags

- Default: fetches all task logs; succeeded tasks are compressed to last 30 lines + error snippets
- `--failed-only`: only fetches logs for failed tasks — fastest mode, but **will miss** errors
  logged in succeeded tasks (use only when you know the pattern is not "collect errors, fail at end")

## Presenting findings

- Lead with the root cause and evidence from the log text
- Quote specific error lines from the logs
- If the error matches a known pattern (see CLAUDE.md error table), include the fix
- For Snowflake deployment errors, check if the user/role exists and suggest YAML or ownership changes
- If root cause came from a succeeded task, call this out explicitly: "The failed task contains
  no diagnostics — the actual error was found in [task name] which reported success"
