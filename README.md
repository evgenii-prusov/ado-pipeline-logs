# ado-pipeline-logs

A Claude Code skill that fetches and analyzes Azure DevOps pipeline logs. Paste a pipeline URL or ask about a build failure -- Claude automatically retrieves the timeline, identifies failed tasks, and presents a root cause analysis with evidence from the logs.

## Prerequisites

- **Python 3.8+** (stdlib only, no pip packages needed)
- **Authentication** (one of):
  - Azure CLI (`az`) with an active session: `az login`
  - Or a Personal Access Token in the `ADO_PAT` environment variable

## Installation

### Method A: Global install (recommended)

```bash
git clone <this-repo-url> ado-pipeline-logs
cd ado-pipeline-logs
bash install.sh
```

This copies the skill to `~/.claude/skills/ado-pipeline-logs/`, making it available in all Claude Code sessions.

### Method B: Project-local install

Copy the skill into a specific project so it's available when working in that directory:

```bash
cp -r skills/ado-pipeline-logs <your-project>/.claude/skills/
```

### Method C: Manual copy

If you prefer not to use the installer:

```bash
mkdir -p ~/.claude/skills/ado-pipeline-logs/scripts
cp skills/ado-pipeline-logs/SKILL.md ~/.claude/skills/ado-pipeline-logs/
cp skills/ado-pipeline-logs/scripts/ado_pipeline_logs.py ~/.claude/skills/ado-pipeline-logs/scripts/
```

## Permission Setup

The skill needs permission to run the Python script via the `Bash` tool. Add this to your project's `.claude/settings.local.json` or global `~/.claude/settings.json`:

```json
{
  "permissions": {
    "allow": [
      "Bash(python3 ~/.claude/skills/ado-pipeline-logs/scripts/ado_pipeline_logs.py:*)"
    ]
  }
}
```

For `az rest` based quick queries (used by the CLAUDE.md instructions), also add:

```json
"Bash(az rest:*)"
```

## Usage

### Automatic (skill trigger)

Just paste an Azure DevOps build URL in Claude Code:

```
https://dev.azure.com/{org}/{project}/_build/results?buildId=123
```

Claude will automatically invoke the skill, fetch logs, and analyze the failure.

### Manual (script directly)

```bash
# From a build URL
python3 ~/.claude/skills/ado-pipeline-logs/scripts/ado_pipeline_logs.py \
  --url "https://dev.azure.com/{org}/{project}/_build/results?buildId=123"

# From explicit args
python3 ~/.claude/skills/ado-pipeline-logs/scripts/ado_pipeline_logs.py \
  --org my-org --project MyProject --build-id 123

# Only fetch logs for failed tasks (faster for large pipelines)
python3 ~/.claude/skills/ado-pipeline-logs/scripts/ado_pipeline_logs.py \
  --url "https://dev.azure.com/{org}/{project}/_build/results?buildId=123" \
  --failed-only
```

## Output Format

The script returns structured JSON:

```json
{
  "build_id": 123,
  "build_url": "https://dev.azure.com/...",
  "definition": "my-pipeline",
  "result": "failed",
  "stages": [
    {
      "name": "Deploy",
      "result": "failed",
      "jobs": [
        {
          "name": "DeployJob",
          "result": "failed",
          "tasks": [
            {
              "name": "Run Migrations",
              "result": "failed",
              "error_count": 1,
              "issues": [{"type": "error", "message": "..."}],
              "log": "... full log text ..."
            }
          ]
        }
      ]
    }
  ],
  "summary": {
    "total_tasks": 15,
    "succeeded": 13,
    "failed": 1,
    "skipped": 1,
    "failed_task_names": ["Run Migrations"]
  }
}
```

Logs over 5000 lines are automatically truncated (first 200 + last 500 lines).

## Authentication

The script tries two methods in order:

1. **Azure CLI token** (preferred): Runs `az account get-access-token --resource 499b84ac-1321-427f-aa17-267ca6975798` to get an AAD token scoped to Azure DevOps. Requires `az login` to have been run.

2. **Personal Access Token**: Falls back to the `ADO_PAT` environment variable. Generate a PAT at `https://dev.azure.com/{org}/_usersSettings/tokens` with **Build (Read)** scope.

### Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `HTTP 401 Unauthorized` | Token expired (~1h lifetime) | Run `az account get-access-token --resource 499b84ac-1321-427f-aa17-267ca6975798` to refresh |
| `No authentication available` | Not logged in and no PAT set | Run `az login` or `export ADO_PAT=<your-token>` |
| `Could not parse URL` | URL format not recognized | Use `https://dev.azure.com/{org}/{project}/_build/results?buildId=123` format |
| Empty stages/tasks | Pipeline has no YAML stages | The script requires YAML-based pipelines with stages |

## CLAUDE.md Integration

For quick ad-hoc queries without the full script, add `az rest` instructions to your project's `CLAUDE.md`. See the included `CLAUDE.md.example` for a template with:
- One-liner auth pattern: `az rest --resource 499b84ac-... --url <ADO_API_URL>`
- Three-step workflow (list builds -> timeline -> logs)
- Common error patterns table

Copy and customize for your org/project:
```bash
cp CLAUDE.md.example <your-project>/CLAUDE.md
# Edit to replace {org}, {project}, {definitionId} with your values
```

## How It Works

1. **Get Timeline**: Calls the ADO Build Timeline API to get all Stage/Phase/Job/Task records
2. **Build Hierarchy**: Reconstructs the 4-level ADO hierarchy (Stage -> Phase -> Job -> Task) from flat records using `parentId`
3. **Fetch Logs**: Retrieves log content for each task (or only failed tasks with `--failed-only`)
4. **Structure Output**: Returns JSON with the full hierarchy, inline issues, and log content
