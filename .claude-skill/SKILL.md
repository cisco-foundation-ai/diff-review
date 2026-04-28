---
name: diff-review
description: Generate a categorized HTML diff viewer for a GitHub PR with intelligent grouping
---

# diff-review

Generate a categorized HTML diff viewer for a GitHub PR with intelligent grouping.

## Usage

Use this skill when a user asks to review a PR with categorized diffs:

```
/diff-review 630
```

Or when they mention:
- "Start review server for PR 678"
- "Review PR 678"
- "Stop all review servers"
- "show me PR 630 organized by category"
- "categorize the changes in PR 630"
- "give me a better view of PR 630"
- "review PR 630 with grouped files"

## What it does

1. **Fetches PR data** from GitHub (all files and diffs)
2. **Categorizes files** intelligently:
   - Uses Claude API if `ANTHROPIC_API_KEY` is available (semantic grouping)
   - Falls back to pattern-based categorization (still very useful)
3. **Generates HTML diff viewer** with:
   - Collapsible sections per category
   - Priority badges (P1=review first, P5=review last)
   - Syntax-highlighted diffs
   - File statistics per category
   - Dark theme (GitHub-style)
4. **Interactive features** (when using `--serve`):
   - 💬 buttons on diff lines post comments directly to GitHub
   - Existing comment indicators on lines with comments (clickable)
   - Live server with on-the-fly HTML generation, no disk clutter
5. **Opens in browser** automatically

## Modes

### Interactive Server Mode (Recommended)
```bash
pr-diff-review 678 --serve

# Custom port
pr-diff-review 678 --serve --port 8888
```
- Runs on `http://localhost:8080` (or custom port)
- Enables inline commenting directly to GitHub
- Shows existing PR comments inline
- Caches HTML after first generation for fast subsequent loads
- Continues until Ctrl+C, port conflict, or process termination

### Offline Mode (Static HTML)
```bash
pr-diff-review 678
```
- Generates static HTML file for sharing/archiving
- No live commenting features

## Requirements

- `gh` CLI authenticated (`gh auth login`)
- `pr-diff-review` package installed (automatically includes all dependencies)
- `ANTHROPIC_API_KEY` env var (optional, enables smarter categorization)

## Authentication

Uses `GITHUB_TOKEN` environment variable or `gh auth token`. Set once:
```bash
export GITHUB_TOKEN=$(gh auth token)
```

## Implementation

When user invokes this skill:

1. Parse PR number from user message
2. Determine mode based on user request:
   - If they say "start review server" or "review PR": use `--serve` (interactive mode)
   - Otherwise: generate static HTML

### For Interactive Server Mode:
1. Run: `pr-diff-review {PR_NUMBER} --serve`
2. The tool will:
   - Detect the current repo
   - Fetch PR data
   - Categorize with LLM (if key available) or patterns
   - Start HTTP server on port 8080
   - Generate HTML on-the-fly

3. Tell the user:
   ```
   ✓ Review server started for PR {NUMBER}

   Access at: http://localhost:8080

   Features:
   - Click 💬 buttons to comment on lines
   - Existing comments shown inline
   - Press Ctrl+C to stop server
   ```

### For Static HTML Mode:
1. Run: `pr-diff-review {PR_NUMBER}`
2. The tool will automatically:
   - Detect the current repo
   - Fetch PR data
   - Categorize with LLM (if key available) or patterns
   - Generate HTML file
   - Tell you where the file is

3. Tell the user:
   ```
   ✓ Generated categorized diff view: pr-{NUMBER}-categorized-diff.html

   Opening in browser...
   ```

4. Open the HTML file with: `open pr-{NUMBER}-categorized-diff.html`

## Example output

When reviewing a multi-tenancy PR, categories might include:
- **Multi-Tenancy Core Infrastructure** (P1) - Organization model, RLS, sessions
- **Authentication & Authorization** (P1) - Auth flow, stale session detection
- **Platform Administration** (P1) - Org management endpoints
- **Service Layer Updates** (P2) - Services updated for org-scoping
- **API Routes** (P2) - Route handlers updated
- **Tests** (P4) - Test updates
- **Documentation** (P5) - README updates

Each category is collapsible with file counts and diff stats.
