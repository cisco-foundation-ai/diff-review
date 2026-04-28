# diff-review

Generate categorized HTML diff viewers for GitHub PRs with intelligent grouping and inline commenting.

## Features

- **Smart categorization**: Uses Claude API or pattern-based analysis to group related files
- **Interactive review server**: Comment directly on lines via GitHub API
- **Syntax highlighting**: Beautiful diff views with GitHub-style theming
- **Priority badges**: P1-P5 badges help focus on critical changes first
- **AST-based detection**: Identifies formatting-only changes
- **Existing comment integration**: Shows inline comments from GitHub

## Installation

```bash
uv pip install pr-diff-review
```

## Usage

### As a CLI tool

```bash
# Interactive server mode (recommended)
pr-diff-review 630 --serve

# Static HTML mode
pr-diff-review 630

# Custom repository
pr-diff-review 630 --repo owner/repo --serve
```

### As a Claude Code skill

Install the skill to any repository:

```bash
pr-diff-review install-skill
```

Then use in Claude Code:

```
/diff-review 630
```

### As a Python module

```python
from pr_diff_review import PRDiffFetcher, LLMCategorizer, HTMLGenerator

fetcher = PRDiffFetcher(repo="owner/repo", pr_number=630)
pr_info, files, diff_hashes = fetcher.fetch()

categorizer = LLMCategorizer()
categories = categorizer.categorize(files, pr_info)

generator = HTMLGenerator()
html = generator.generate(pr_info, categories, diff_hashes)
```

## Requirements

- Python 3.10+
- `gh` CLI authenticated (`gh auth login`)
- Optional: `ANTHROPIC_API_KEY` for smarter categorization
- Optional: `OPENAI_API_KEY` as fallback

## Authentication

The tool uses GitHub authentication from:
1. `GITHUB_TOKEN` environment variable
2. `gh auth token` (if gh CLI is authenticated)

## Development

```bash
# Clone and install dev dependencies
git clone https://github.com/yourusername/diff-review.git
cd diff-review
uv venv
uv pip install -e ".[dev]"

# Run tests
pytest

# Run linters
ruff check pr_diff_review --fix
ruff format pr_diff_review
mypy pr_diff_review
```

## License

MIT
