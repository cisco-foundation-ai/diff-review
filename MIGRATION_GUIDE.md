# Migration Guide: From fai-service to diff-review Package

This guide explains how to migrate from using the embedded `tools/pr-category-diff.py` script to the standalone `pr-diff-review` package.

## What Changed

### Before (Embedded in fai-service)

```bash
# In fai-service repo
./tools/pr-category-diff.py 630 --serve
```

### After (Standalone Package)

```bash
# Install once
uv pip install pr-diff-review

# Use anywhere
pr-diff-review 630 --serve
```

## Migration Steps for Existing Projects

### 1. Install the Package

In your project's Python environment:

```bash
cd /path/to/your/project
uv pip install pr-diff-review
# or for local development
uv pip install -e /path/to/diff-review
```

### 2. Install the Claude Code Skill

```bash
pr-diff-review install-skill
```

This creates `.claude/skills/diff-review/SKILL.md` in your project.

### 3. Update `.gitignore` (if needed)

The skill file should be committed:

```gitignore
# Don't ignore Claude Code skills
!.claude/skills/
```

### 4. Remove Old Files (Optional)

If you were using the embedded version in fai-service, you can now remove:

- `tools/pr-category-diff.py`
- `tools/pr_diff_server.py`
- `tools/static/pr-diff-viewer.*`
- `.claude/skills/diff-review/` (will be replaced by skill install)

**Note**: Only do this if you're sure no other code depends on these files.

## For fai-service Repository

### Current State

The fai-service repo still contains the original implementation in `tools/`.

### Recommended Changes

1. **Install the package**:
   ```bash
   cd backend
   uv add pr-diff-review --group dev
   ```

2. **Update the skill**:
   ```bash
   pr-diff-review install-skill
   ```

3. **Keep or remove originals**:
   - **Option A**: Keep originals for backward compatibility during transition
   - **Option B**: Remove originals and update documentation to reference the package

4. **Update CLAUDE.md**:
   Reference the new package in any development guidelines.

## API Compatibility

The CLI interface is identical:

| Old Command | New Command |
|-------------|-------------|
| `./tools/pr-category-diff.py 630` | `pr-diff-review 630` |
| `./tools/pr-category-diff.py 630 --serve` | `pr-diff-review 630 --serve` |
| `./tools/pr-category-diff.py 630 --no-llm` | `pr-diff-review 630 --no-llm` |
| `/diff-review 630` (Claude) | `/diff-review 630` (unchanged) |

## Programmatic Usage

The package can now be imported and used programmatically:

```python
from pr_diff_review import (
    PRDiffFetcher,
    LLMCategorizer,
    HTMLGenerator,
    PRDiffServer,
)

# Fetch PR data
fetcher = PRDiffFetcher(repo="owner/repo", pr_number=630)
pr_info, files, diff_hashes = fetcher.fetch_all()

# Categorize
categorizer = LLMCategorizer()
categories = categorizer.categorize(pr_info, files)

# Generate HTML
generator = HTMLGenerator(embed_assets=True)
generator.generate(pr_info, categories, Path("output.html"), diff_hashes)

# Or start server
server = PRDiffServer(
    pr_info=pr_info,
    files=files,
    diff_hashes=diff_hashes,
    categories=categories,
    repo="owner/repo",
    pr_number=630,
    commit_sha=fetcher.head_sha,
    port=8080,
)
server.start()
```

## Benefits of Migration

1. **Reusability**: Use in any project without copying files
2. **Versioning**: Track package versions independently
3. **Updates**: Single `pip install --upgrade` updates all projects
4. **Dependencies**: Package manages its own dependencies
5. **Distribution**: Easy to share with other teams

## Troubleshooting

### Import Errors

If you see `ModuleNotFoundError: No module named 'pr_diff_review'`:

```bash
# Check installation
uv pip list | grep pr-diff-review

# Reinstall if needed
uv pip install --force-reinstall pr-diff-review
```

### Skill Not Found

If Claude Code doesn't see the skill:

```bash
# Verify skill file exists
ls -la .claude/skills/diff-review/

# Reinstall skill
pr-diff-review install-skill

# Restart Claude Code if using desktop app
```

### GitHub Authentication

The package uses the same authentication as before:

```bash
# Via gh CLI
gh auth login

# Or via environment variable
export GITHUB_TOKEN=$(gh auth token)
```

## Rollback

If you need to rollback to the embedded version:

```bash
# Uninstall package
uv pip uninstall pr-diff-review

# Use original script
./tools/pr-category-diff.py 630 --serve
```
