# GitHub Issue Synchronization

Debussy can automatically synchronize GitHub issue status with your orchestration workflow. When phases start and complete, linked GitHub issues receive label updates reflecting the execution state.

## Quick Start

1. **Set your GitHub token:**
   ```bash
   export GITHUB_TOKEN=ghp_your_token_here
   ```

2. **Enable GitHub sync in your config** (`.debussy/config.yaml`):
   ```yaml
   github:
     enabled: true
   ```

3. **Link issues in your master plan:**
   ```markdown
   # My Feature - Master Plan

   **GitHub Issues:** #10, #11, #12
   **GitHub Repo:** owner/repo

   ## Phases
   ...
   ```

4. **Run your plan:**
   ```bash
   debussy run plans/my-feature/MASTER_PLAN.md
   ```

Issues will automatically receive `debussy:in-progress` → `debussy:completed` labels as phases execute.

## Configuration

### Config File (`.debussy/config.yaml`)

```yaml
github:
  # Enable/disable GitHub sync (default: false)
  enabled: true

  # Auto-close issues when ALL phases complete (default: false)
  auto_close: false

  # Create labels if they don't exist (default: true)
  create_labels_if_missing: true

  # Preview operations without executing (default: false)
  dry_run: false

  # Custom label names and colors
  labels:
    in_progress: "debussy:in-progress"
    completed: "debussy:completed"
    failed: "debussy:failed"
    color_in_progress: "1D76DB"  # Blue
    color_completed: "0E8A16"    # Green
    color_failed: "D93F0B"       # Red
```

### CLI Flags

```bash
# Enable auto-close for a single run
debussy run MASTER_PLAN.md --auto-close

# Preview sync operations without executing
debussy run MASTER_PLAN.md --dry-run-sync
```

## Master Plan Format

Link GitHub issues using any of these formats in your master plan:

```markdown
# Feature Name - Master Plan

**GitHub Issues:** #10, #11, #12
**GitHub Repo:** owner/repo
```

Or with full URLs:
```markdown
**GitHub Issues:** https://github.com/owner/repo/issues/10
```

Or gh-style refs:
```markdown
**github_issues:** gh#10, gh#11
```

### Auto-Detection

If `GitHub Repo` is not specified, Debussy will attempt to detect it from your git remote:
```bash
git remote get-url origin
```

## Label Behavior

### Label Transitions

| Event | Label Change |
|-------|--------------|
| Phase starts | → `debussy:in-progress` |
| Phase completes | → `debussy:completed` |
| Phase fails | → `debussy:failed` |

Labels are updated atomically—old state labels are removed before new ones are added.

### Auto-Close (Optional)

When `auto_close: true` or `--auto-close` is used, linked issues are closed with a completion comment when ALL phases complete successfully.

```yaml
github:
  enabled: true
  auto_close: true
```

**Safety:** Auto-close only triggers on full plan completion, never on individual phase completion.

## Milestone Progress

If linked issues have a milestone, Debussy will update the milestone description with progress:

```
📊 **Debussy Progress:** 75% (3/4 phases)
```

The milestone is detected from the first linked issue that has one.

## Authentication

### Using GITHUB_TOKEN

Set the `GITHUB_TOKEN` environment variable:

```bash
# In your shell profile (~/.bashrc, ~/.zshrc)
export GITHUB_TOKEN=ghp_your_token_here

# Or for a single run
GITHUB_TOKEN=ghp_... debussy run MASTER_PLAN.md
```

### Required Scopes

The token needs these GitHub permissions:
- `repo` - For private repositories
- `public_repo` - For public repositories only

### Using gh CLI Auth

If you're already authenticated with `gh auth login`, you can use that token:

```bash
export GITHUB_TOKEN=$(gh auth token)
```

## Error Handling

### Rate Limiting

Debussy implements automatic retry with exponential backoff when rate limits are hit. For typical plans (3-5 phases, 2-5 issues), rate limits are unlikely to trigger.

### Network Failures

Network errors are retried up to 3 times with exponential backoff. If all retries fail, the sync operation logs a warning but does not fail the phase.

### Invalid Issue References

Invalid issue numbers are logged as warnings during initialization. Sync continues with valid issues only.

## Dry Run Mode

Preview sync operations without executing them:

```bash
debussy run MASTER_PLAN.md --dry-run-sync
```

Or in config:
```yaml
github:
  enabled: true
  dry_run: true
```

Dry run mode will log all planned operations:
```
[DRY RUN] Would set labels on #10: ['debussy:in-progress']
[DRY RUN] Would update milestone #1 description
```

## Troubleshooting

### "No GitHub token provided"

Set the `GITHUB_TOKEN` environment variable:
```bash
export GITHUB_TOKEN=ghp_your_token_here
```

### "GitHub sync enabled but no repo specified/detected"

Either:
1. Add `**GitHub Repo:** owner/repo` to your master plan
2. Ensure your git remote is configured: `git remote -v`

### "Issue #X not accessible"

Check that:
1. The issue number exists
2. Your token has permission to read the repository
3. For private repos, the token has `repo` scope

### Labels not appearing

Ensure `create_labels_if_missing: true` (default) in your config. Labels are created automatically on first use.

## Disabling Sync

To disable GitHub sync:

1. **In config:**
   ```yaml
   github:
     enabled: false
   ```

2. **Remove linked issues from plan:**
   Delete the `**GitHub Issues:**` line from your master plan.

3. **Manual label cleanup:**
   ```bash
   gh issue edit 10 --remove-label "debussy:in-progress,debussy:completed,debussy:failed"
   ```
