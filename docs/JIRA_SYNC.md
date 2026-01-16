# Jira Issue Synchronization

Debussy can automatically transition Jira issues through your workflow states when phases start and complete. This keeps your issue tracking synchronized with actual development progress without manual status updates.

## Quick Start

1. **Get a Jira API Token**
   - Go to https://id.atlassian.com/manage-profile/security/api-tokens
   - Click "Create API token"
   - Copy the token value

2. **Set Environment Variables**
   ```bash
   export JIRA_EMAIL="your-email@company.com"
   export JIRA_API_TOKEN="your-api-token"
   ```

3. **Configure Debussy**
   Create or edit `.debussy/config.yaml`:
   ```yaml
   jira:
     enabled: true
     url: https://your-company.atlassian.net
     dry_run: true  # Start with dry run to test
     transitions:
       on_phase_start: "In Development"
       on_phase_complete: "Code Review"
       on_plan_complete: "Done"
   ```

4. **Link Issues in Your Plan**
   In your master plan file, add:
   ```markdown
   **Jira Issues:** PROJ-123, PROJ-124
   ```

5. **Run Debussy**
   ```bash
   debussy run docs/plans/feature-MASTER_PLAN.md
   ```

## Configuration

### Full Configuration Example

```yaml
jira:
  # Enable/disable Jira sync
  enabled: true

  # Your Jira instance URL
  url: https://your-company.atlassian.net

  # Start in dry-run mode for testing
  dry_run: false

  # Workflow transitions for phase lifecycle events
  transitions:
    # Transition when a phase starts executing
    on_phase_start: "In Development"

    # Transition when a phase completes successfully
    on_phase_complete: "Code Review"

    # Transition when all phases complete
    on_plan_complete: "Done"
```

### Transition Configuration

Transition names must match **exactly** what appears in your Jira workflow. To find available transitions:

1. Open an issue in Jira
2. Click the status dropdown (e.g., "To Do")
3. Note the exact names shown (e.g., "Start Progress", "In Development")

Alternatively, use the Jira REST API:
```bash
curl -u $JIRA_EMAIL:$JIRA_API_TOKEN \
  "https://your-company.atlassian.net/rest/api/3/issue/PROJ-123/transitions" \
  | jq '.transitions[].name'
```

### Plan Metadata

Link Jira issues in your master plan file using any of these formats:

```markdown
# Feature Name - Master Plan

**Jira Issues:** PROJ-123, PROJ-124
```

Or with explicit list:
```markdown
**jira_issues:** [PROJ-123, PROJ-124, DEV-456]
```

Or inline with text:
```markdown
Jira Issues: Implementing feature for PROJ-123 and related DEV-456
```

The parser extracts all PROJECT-NUMBER patterns automatically.

## How It Works

### Phase Lifecycle Events

1. **Phase Start**: When Debussy begins executing a phase, it transitions all linked issues to the `on_phase_start` state (e.g., "In Development")

2. **Phase Complete**: When a phase passes compliance checks, issues transition to `on_phase_complete` state (e.g., "Code Review")

3. **Plan Complete**: After all phases finish successfully, issues transition to `on_plan_complete` state (e.g., "Done")

### Error Handling

Jira sync is designed to be non-blocking:

- **Invalid transitions**: If a transition isn't available (wrong workflow state), Debussy logs a warning and continues. The phase won't fail.

- **Network errors**: Temporary failures are retried with exponential backoff (up to 3 attempts).

- **Missing issues**: Issues that don't exist or aren't accessible are skipped during initialization.

### Dry Run Mode

Always start with `dry_run: true` to verify configuration:

```yaml
jira:
  enabled: true
  url: https://your-company.atlassian.net
  dry_run: true  # Will log but not execute transitions
```

Output will show:
```
[dim]Jira: [DRY RUN] Would transition PROJ-123 via 'In Development' (phase 1 start)[/dim]
```

## Troubleshooting

### "No Jira API token provided"

Set the `JIRA_API_TOKEN` environment variable:
```bash
export JIRA_API_TOKEN="your-token"
```

For CI/CD, use secrets management to inject the token.

### "No Jira email provided"

Set the `JIRA_EMAIL` environment variable:
```bash
export JIRA_EMAIL="your-email@company.com"
```

### "Transition 'X' not available for ISSUE-123"

The transition name doesn't match your workflow. Common causes:

1. **Typo**: Check the exact transition name in Jira
2. **Wrong state**: Issue may already be in that state, or the transition isn't valid from the current state
3. **Workflow conditions**: Some transitions have conditions (e.g., "all subtasks completed")

To debug, check available transitions:
```bash
curl -u $JIRA_EMAIL:$JIRA_API_TOKEN \
  "https://your-company.atlassian.net/rest/api/3/issue/PROJ-123/transitions"
```

### "Jira access forbidden"

Your API token may lack permissions. Ensure your user has:
- Read access to issues
- Transition permission for the project

### "Jira sync enabled but no issues linked in plan"

Add Jira issues to your master plan:
```markdown
**Jira Issues:** PROJ-123
```

### Transitions Not Being Cached

Transitions are cached per issue to minimize API calls. If you need fresh data (e.g., after manual status change), Debussy will fetch transitions again when the cache is invalidated after a successful transition.

## API Token Permissions

The Jira API token needs minimal permissions:

- **Browse projects**: Read issue details
- **Transition issues**: Perform workflow transitions

The token inherits your user's permissions. No admin access is required.

## Security Best Practices

1. **Never commit tokens**: Use environment variables or secrets management

2. **Use a service account**: Create a dedicated Jira user for automation with minimal permissions

3. **Rotate tokens regularly**: Jira tokens don't expire, but regular rotation is good practice

4. **Audit access**: Review the service account's activity periodically

## Example Workflow

Typical Jira workflow integration:

```
To Do → In Development → Code Review → QA Testing → Done
         ↑                ↑             ↑           ↑
         |                |             |           |
   phase start    phase complete    (manual)    plan complete
```

Configuration:
```yaml
jira:
  enabled: true
  url: https://acme.atlassian.net
  transitions:
    on_phase_start: "In Development"
    on_phase_complete: "Code Review"
    on_plan_complete: "Done"
```

This automates the development portion while leaving QA as a manual step.
