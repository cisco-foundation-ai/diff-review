# Setup Guide

## Development Setup

1. **Clone and install**:
   ```bash
   git clone <repo-url>
   cd diff-review
   uv venv
   source .venv/bin/activate  # or `.venv\Scripts\activate` on Windows
   uv pip install -e ".[dev]"
   ```

2. **Run tests**:
   ```bash
   pytest
   ```

3. **Run linters**:
   ```bash
   ruff check pr_diff_review --fix
   ruff format pr_diff_review
   mypy pr_diff_review
   ```

## Using in Another Project

### Option 1: Install from Git

```bash
uv pip install git+https://github.com/cisco-foundation-ai/diff-review.git
```

### Option 2: Install Locally for Development

```bash
cd /path/to/diff-review
uv pip install -e .
```

### Install the Claude Code Skill

After installing the package, install the skill to your repo:

```bash
cd /path/to/your/repo
pr-diff-review install-skill
```

This creates `.claude/skills/diff-review/SKILL.md` in your current repo.

## Usage

### As a CLI Tool

```bash
# Interactive server mode
pr-diff-review 630 --serve

# Static HTML
pr-diff-review 630

# Custom repo
pr-diff-review 630 --repo owner/repo
```

### As a Claude Code Skill

Once installed:

```
/diff-review 630
```

### As a Python Module

```python
from pr_diff_review import PRDiffFetcher, LLMCategorizer, HTMLGenerator

fetcher = PRDiffFetcher(repo="owner/repo", pr_number=630)
pr_info, files, diff_hashes = fetcher.fetch_all()

categorizer = LLMCategorizer()
categories = categorizer.categorize(pr_info, files)

generator = HTMLGenerator(embed_assets=True)
generator.generate(pr_info, categories, Path("output.html"), diff_hashes)
```

## Environment Variables

- `ANTHROPIC_API_KEY` - Claude API key (optional, for smart categorization)
- `OPENAI_API_KEY` - OpenAI API key (fallback)
- `GITHUB_TOKEN` - GitHub token (or use `gh auth login`)
- `VERIFY_SSL` - Set to `1` to enable SSL verification for GitHub API

## Package Structure

```
pr_diff_review/
├── __init__.py          # Package exports
├── models.py            # Data classes (PRFile, Category)
├── fetcher.py           # GitHub PR fetching
├── ast_comparer.py      # AST-based diff analysis
├── categorizer.py       # File categorization logic
├── html_generator.py    # HTML diff viewer generation
├── server.py            # HTTP server for interactive mode
├── s3_uploader.py       # S3 upload utilities
├── static/              # CSS, JS assets
│   ├── pr-diff-viewer.css
│   ├── pr-diff-viewer.js
│   └── prism-github-theme.css
└── cli/
    ├── __init__.py
    └── main.py          # CLI entry point

.claude-skill/
└── SKILL.md            # Claude Code skill definition

tests/
└── test_imports.py     # Basic import tests
```

## Publishing

To publish to PyPI:

```bash
# Build
uv build

# Upload to PyPI
uv publish
```
