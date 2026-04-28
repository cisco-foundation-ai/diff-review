# Quick Start Guide

Get up and running with `pr-diff-review` in under 2 minutes.

## Prerequisites

- Python 3.10 or later
- `gh` CLI authenticated (`gh auth login`)

## Installation

```bash
uv pip install git+https://github.com/cisco-foundation-ai/diff-review.git
```

Or for local development:

```bash
git clone https://github.com/cisco-foundation-ai/diff-review.git
cd diff-review
uv pip install -e .
```

## Basic Usage

### 1. Generate Static HTML Diff

```bash
pr-diff-review 630
```

Output: `pr-630-categorized-diff.html`

### 2. Start Interactive Review Server

```bash
pr-diff-review 630 --serve
```

Then open `http://localhost:8080` in your browser.

Features:
- 💬 Click buttons to comment on lines
- View existing GitHub comments inline
- Live HTML generation (no disk files)

### 3. Use with Claude Code

Install the skill once per repository:

```bash
cd /path/to/your/repo
pr-diff-review install-skill
```

Then use in Claude Code:

```
/diff-review 630
```

## Configuration

### GitHub Authentication

The tool uses GitHub CLI authentication automatically:

```bash
gh auth login
```

Or set a token:

```bash
export GITHUB_TOKEN=$(gh auth token)
```

### Enable LLM Categorization

For smarter file categorization, set an API key:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
# or
export OPENAI_API_KEY=sk-...
```

Without an API key, the tool falls back to pattern-based categorization (still useful).

## Common Commands

```bash
# Review PR in current repo
pr-diff-review 630

# Review PR in different repo
pr-diff-review 630 --repo owner/repo

# Custom output file
pr-diff-review 630 --output my-review.html

# Skip LLM, use patterns only
pr-diff-review 630 --no-llm

# Server with custom port
pr-diff-review 630 --serve --port 8888

# Install Claude Code skill
pr-diff-review install-skill
```

## What You Get

### Categorized Diff View

Files are intelligently grouped by:
- **Feature areas** (auth, API, database, frontend, etc.)
- **Priority** (P1=critical, P5=minor)
- **Change type** (logic, tests, docs, config)

### Interactive Features (Server Mode)

- **Inline commenting**: Click 💬 on any line to post to GitHub
- **Existing comments**: See PR comments inline with links
- **Live generation**: No HTML files littering your workspace
- **Dark theme**: Easy on the eyes

### Smart Detection

- **Formatting-only changes**: Marked with "🎨 Formatting only"
- **AST-aware**: Detects semantic vs. cosmetic changes
- **Context expansion**: Shows surrounding code for better understanding

## Troubleshooting

### "ModuleNotFoundError: No module named 'pr_diff_review'"

```bash
uv pip install --force-reinstall pr-diff-review
```

### "gh CLI not authenticated"

```bash
gh auth login
```

### "Port already in use"

```bash
pr-diff-review 630 --serve --port 8888
```

### Skill not found in Claude Code

```bash
pr-diff-review install-skill
# Then restart Claude Code
```

## Next Steps

- Read [README.md](README.md) for full feature list
- Check [SETUP.md](SETUP.md) for development setup
- See [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) if migrating from embedded version
- Review [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) for technical details

## Examples

### Example 1: Quick Review

```bash
# Fetch and categorize PR #750
pr-diff-review 750

# Opens pr-750-categorized-diff.html in browser
```

### Example 2: Team Review Session

```bash
# Start server for PR #750
pr-diff-review 750 --serve

# Share URL with team: http://localhost:8080
# Team members can comment inline
# Press Ctrl+C when done
```

### Example 3: Cross-Repo Review

```bash
# Review a PR from a different repo
pr-diff-review 123 --repo facebook/react

# Or set as default
export PR_DIFF_REPO=facebook/react
pr-diff-review 123
```

### Example 4: Python API

```python
from pathlib import Path
from pr_diff_review import PRDiffFetcher, LLMCategorizer, HTMLGenerator

# Fetch PR data
fetcher = PRDiffFetcher(repo="owner/repo", pr_number=630)
pr_info, files, diff_hashes = fetcher.fetch_all()

# Categorize with Claude
import os
categorizer = LLMCategorizer(os.getenv("ANTHROPIC_API_KEY"))
categories = categorizer.categorize(pr_info, files)

# Generate HTML
generator = HTMLGenerator(embed_assets=True)
generator.generate(pr_info, categories, Path("my-review.html"), diff_hashes)
```

## Support

- **Issues**: File on GitHub Issues
- **Questions**: Open a GitHub Discussion
- **PRs**: Contributions welcome!

## License

MIT License - see [LICENSE](LICENSE)
