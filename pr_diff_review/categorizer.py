import json
import re
import sys
from collections import Counter
from fnmatch import fnmatch
from typing import Any

from pr_diff_review.models import PRFile, Category

try:
    import anthropic
except ImportError:
    anthropic = None  # type: ignore[assignment]

try:
    import openai
except ImportError:
    openai = None  # type: ignore[assignment]


class PatternCategorizer:
    """Fallback categorization using file path patterns"""

    CATEGORIES = [
        {
            "name": "Database & Models",
            "description": "Database schema, models, and migrations",
            "patterns": ["*/models.py", "*/alembic/*", "*/migrations/*"],
            "priority": 1,
        },
        {
            "name": "Core Infrastructure",
            "description": "Core application infrastructure and configuration",
            "patterns": ["*/core/*", "*/config.py", "*/db.py"],
            "priority": 1,
        },
        {
            "name": "Authentication & Authorization",
            "description": "Auth, sessions, and permission handling",
            "patterns": ["*/auth.py", "*/deps.py", "*/session*"],
            "priority": 1,
        },
        {
            "name": "API Routes",
            "description": "HTTP route handlers and controllers",
            "patterns": ["*/api/routes/*", "*/controllers/*"],
            "priority": 2,
        },
        {
            "name": "Services & Business Logic",
            "description": "Service layer and business logic",
            "patterns": ["*/services/*"],
            "priority": 2,
        },
        {
            "name": "Repositories & Data Access",
            "description": "Data access layer and repository pattern",
            "patterns": ["*/repositories/*", "*/crud/*"],
            "priority": 2,
        },
        {
            "name": "Schemas & DTOs",
            "description": "Request/response schemas and data transfer objects",
            "patterns": ["*/schemas/*"],
            "priority": 3,
        },
        {
            "name": "Tests",
            "description": "Test files and test utilities",
            "patterns": ["*/tests/*", "*_test.py", "test_*.py", "*/conftest.py"],
            "priority": 4,
        },
        {
            "name": "Infrastructure & Deployment",
            "description": "CI/CD, Docker, Kubernetes, Terraform",
            "patterns": [
                ".github/workflows/*",
                "Dockerfile*",
                "docker-compose*",
                "*/deployments/*",
                "*/infra/*",
                "*.tf",
                "*/charts/*",
            ],
            "priority": 2,
        },
        {
            "name": "Frontend",
            "description": "Frontend application code",
            "patterns": ["frontend/*", "*/components/*", "*.tsx", "*.jsx", "*.vue"],
            "priority": 2,
        },
        {
            "name": "Documentation",
            "description": "Documentation and README files",
            "patterns": ["*.md", "docs/*", "*.txt"],
            "priority": 5,
        },
    ]

    def categorize(self, files: list[PRFile]) -> list[Category]:
        """Categorize files using pattern matching"""
        categories_dict = {
            cat["name"]: Category(
                name=cat["name"],  # type: ignore[arg-type]
                description=cat["description"],  # type: ignore[arg-type]
                files=[],
                priority=cat["priority"],  # type: ignore[arg-type]
            )
            for cat in self.CATEGORIES
        }

        # Add "Other" category for unmatched files
        categories_dict["Other"] = Category(
            name="Other",
            description="Files that don't match other categories",
            files=[],
            priority=10,
        )

        for pr_file in files:
            matched = False
            for cat_def in self.CATEGORIES:
                if self._matches_patterns(pr_file.path, cat_def["patterns"]):  # type: ignore[arg-type]
                    categories_dict[cat_def["name"]].files.append(pr_file)
                    matched = True
                    break

            if not matched:
                categories_dict["Other"].files.append(pr_file)

        # Filter out empty categories and sort by priority
        result = [cat for cat in categories_dict.values() if cat.files]
        result.sort(key=lambda c: (c.priority, c.name))
        return result

    def _matches_patterns(self, file_path: str, patterns: list[str]) -> bool:
        """Check if file path matches any pattern"""
        from fnmatch import fnmatch

        return any(fnmatch(file_path, pattern) for pattern in patterns)


class PatternDetector:
    """Detect common patterns across diffs to help LLM categorization"""

    @staticmethod
    def detect_patterns(files: list[PRFile]) -> str:
        """Analyze diffs to find common patterns and return a summary"""
        import re
        from collections import Counter

        added_identifiers = []
        removed_identifiers = []
        added_imports = []
        removed_imports = []
        file_groups: dict[str, list[str]] = {}

        # Regex patterns for detection
        identifier_pattern = r"\b[a-z_][a-z0-9_]{2,}\b"
        import_pattern = r"(?:from\s+[\w.]+\s+)?import\s+([\w,\s.]+)"

        for file in files:
            if not file.diff:
                continue

            # Group files by directory for path-based patterns
            directory = "/".join(file.path.split("/")[:-1])
            if directory not in file_groups:
                file_groups[directory] = []
            file_groups[directory].append(file.path)

            for line in file.diff.split("\n"):
                # Analyze added lines
                if line.startswith("+") and not line.startswith("+++"):
                    content = line[1:].strip()

                    # Find identifiers in added lines
                    identifiers = re.findall(identifier_pattern, content)
                    added_identifiers.extend(identifiers)

                    # Find imports in added lines
                    imports = re.findall(import_pattern, content)
                    for imp in imports:
                        added_imports.extend([i.strip() for i in imp.split(",")])

                # Analyze removed lines
                elif line.startswith("-") and not line.startswith("---"):
                    content = line[1:].strip()

                    # Find identifiers in removed lines
                    identifiers = re.findall(identifier_pattern, content)
                    removed_identifiers.extend(identifiers)

                    # Find imports in removed lines
                    imports = re.findall(import_pattern, content)
                    for imp in imports:
                        removed_imports.extend([i.strip() for i in imp.split(",")])

        # Count frequencies
        added_counter = Counter(added_identifiers)
        removed_counter = Counter(removed_identifiers)
        added_imports_counter = Counter(added_imports)

        # Build pattern summary
        patterns = []

        # Common additions (identifiers appearing in 3+ files)
        common_additions = [
            (word, count)
            for word, count in added_counter.most_common(20)
            if count >= 3 and len(word) > 3  # Filter noise
        ]
        if common_additions:
            patterns.append("**Common Additions Across Files:**")
            for word, count in common_additions[:10]:
                patterns.append(f"  - `{word}` added in {count} locations")

        # Common removals (identifiers appearing in 3+ files)
        common_removals = [
            (word, count)
            for word, count in removed_counter.most_common(20)
            if count >= 3 and len(word) > 3
        ]
        if common_removals:
            patterns.append("\n**Common Removals Across Files:**")
            for word, count in common_removals[:10]:
                patterns.append(f"  - `{word}` removed from {count} locations")

        # Common imports added
        if added_imports_counter:
            top_imports = [
                (imp, count)
                for imp, count in added_imports_counter.most_common(10)
                if count >= 2
            ]
            if top_imports:
                patterns.append("\n**Frequently Added Imports:**")
                for imp, count in top_imports[:5]:
                    patterns.append(f"  - `{imp}` added in {count} files")

        # Files grouped by directory (3+ files in same dir)
        dir_groups = [
            (dir_path, files_in_dir)
            for dir_path, files_in_dir in file_groups.items()
            if len(files_in_dir) >= 3
        ]
        if dir_groups:
            patterns.append("\n**Directory Clusters (3+ files changed):**")
            for dir_path, files_in_dir in sorted(dir_groups, key=lambda x: -len(x[1]))[
                :5
            ]:
                patterns.append(f"  - `{dir_path}/` ({len(files_in_dir)} files)")

        # Refactoring hints based on patterns
        refactoring_hints = []

        # Detect user -> org refactoring
        if any(
            word in ["organization", "org_id", "organization_id"]
            for word, _ in common_additions
        ):
            if any(word in ["user", "user_id"] for word, _ in common_removals):
                refactoring_hints.append(
                    "  - **Multi-tenancy refactoring**: user → organization model migration"
                )

        # Detect schema changes
        if any("alembic" in file.path or "migration" in file.path for file in files):
            refactoring_hints.append(
                "  - **Database schema changes**: migrations detected"
            )

        # Detect test changes
        test_files = [f for f in files if "test" in f.path.lower()]
        if len(test_files) >= 5:
            refactoring_hints.append(
                f"  - **Extensive test updates**: {len(test_files)} test files modified"
            )

        if refactoring_hints:
            patterns.append("\n**Detected Refactoring Patterns:**")
            patterns.extend(refactoring_hints)

        return "\n".join(patterns) if patterns else "No significant patterns detected."


class LLMCategorizer:
    """Categorize files using Claude API"""

    def __init__(self, api_key: str):
        if not anthropic:
            raise ImportError("anthropic package not installed")
        self.client = anthropic.Anthropic(api_key=api_key)

    def categorize(
        self, pr_info: dict[str, Any], files: list[PRFile]
    ) -> list[Category]:
        """Categorize files using LLM analysis"""

        # Detect common patterns across all files
        patterns_summary = PatternDetector.detect_patterns(files)

        # Prepare file summary for LLM with more diff context
        file_summary = []
        for f in files:
            file_summary.append(
                {
                    "path": f.path,
                    "additions": f.additions,
                    "deletions": f.deletions,
                    "status": f.status,
                    "diff_preview": f.diff[:1000]
                    if f.diff
                    else "",  # First 1000 chars for better context
                }
            )

        prompt = f"""Analyze this GitHub Pull Request and categorize the changed files into logical groups.

CROSS-FILE PATTERNS DETECTED:
{patterns_summary}

Use these patterns to identify related changes that should be grouped together.
For example, if 20 files all add 'org_id', they likely belong in the same category.

---

Analyze this GitHub Pull Request and categorize the changed files into logical groups.

IMPORTANT: For each category, provide a detailed summary that will help reviewers understand:
1. What specifically changed in this category (be concrete, mention key functions/classes/patterns)
2. Why these changes were made (connect to PR description/goals)
3. What reviewers should pay attention to (edge cases, breaking changes, new patterns)
4. Any design decisions or architectural implications

Use the PR description and diffs to provide rich, actionable summaries.

PR Title: {pr_info["title"]}
PR Description:
{pr_info.get("body", "No description")[:1000]}

Changed Files ({len(files)} total):
{json.dumps(file_summary, indent=2)}

Please categorize these files into logical groups that would help a reviewer understand the PR structure. For each category:
1. Name it clearly (e.g., "Authentication & Sessions", "Database Schema", "API Routes")
2. Provide a brief description (one sentence)
3. Provide a detailed_summary (3-5 bullet points) that explains:
   - Specific changes made (mention key functions, classes, patterns)
   - Why these changes matter (connect to PR goals)
   - What reviewers should focus on (edge cases, breaking changes)
   - Design decisions or architectural implications
4. Assign a priority (1=highest, review first; 5=lowest, review last)
5. List which file paths belong to it

Focus on semantic grouping based on what changed, not just file paths. For example:
- If multiple services changed to add org_id, group as "Multi-tenancy Service Updates"
- If auth and session logic changed together, group as "Authentication System"
- Separate critical infrastructure changes from minor updates

Return ONLY a JSON array with this structure:
[
  {{
    "name": "Category Name",
    "description": "One-sentence summary",
    "detailed_summary": "**What Changed:**\\n- Bullet point 1\\n- Bullet point 2\\n\\n**Why It Matters:**\\n- Reason 1\\n\\n**Review Focus:**\\n- What to look for",
    "priority": 1,
    "file_paths": ["path/to/file1.py", "path/to/file2.py"]
  }}
]

Be concrete and actionable. Aim for 5-8 categories for a large PR."""

        try:
            message = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )

            # Handle different content block types
            content_block = message.content[0]
            if hasattr(content_block, "text"):
                response_text = content_block.text.strip()
            else:
                response_text = str(content_block).strip()

            # Extract JSON from response (handle markdown code blocks)
            if "```json" in response_text:
                response_text = (
                    response_text.split("```json")[1].split("```")[0].strip()
                )
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()

            category_defs = json.loads(response_text)

            # Build categories
            categories = []
            file_map = {f.path: f for f in files}

            for cat_def in category_defs:
                cat_files = [
                    file_map[path] for path in cat_def["file_paths"] if path in file_map
                ]
                if cat_files:
                    categories.append(
                        Category(
                            name=cat_def["name"],
                            description=cat_def["description"],
                            files=cat_files,
                            priority=cat_def.get("priority", 5),
                            detailed_summary=cat_def.get("detailed_summary", ""),
                        )
                    )

            # Check for uncategorized files and do a second pass
            categorized_paths = {f.path for cat in categories for f in cat.files}
            uncategorized = [f for f in files if f.path not in categorized_paths]

            if uncategorized and len(uncategorized) < len(files):
                # Second pass: Try to categorize remaining files
                print(
                    f"  Second pass: categorizing {len(uncategorized)} remaining files...",
                    file=sys.stderr,
                )
                categories = self._second_pass_categorization(
                    pr_info, uncategorized, categories
                )
            elif uncategorized:
                # All files are uncategorized - add to "Other"
                categories.append(
                    Category(
                        name="Other",
                        description="Files not categorized by LLM analysis",
                        files=uncategorized,
                        priority=10,
                    )
                )

            categories.sort(key=lambda c: (c.priority, c.name))
            return categories

        except Exception as e:
            print(f"Warning: LLM categorization failed: {e}", file=sys.stderr)
            print("Falling back to pattern-based categorization...", file=sys.stderr)
            return PatternCategorizer().categorize(files)

    def _second_pass_categorization(
        self,
        pr_info: dict[str, Any],
        uncategorized: list[PRFile],
        existing_categories: list[Category],
    ) -> list[Category]:
        """Second pass: categorize remaining files by assigning to existing or new categories"""

        # Build summary of existing categories
        existing_cat_summary = []
        for i, cat in enumerate(existing_categories):
            file_count = len(cat.files)
            existing_cat_summary.append(
                f"{i + 1}. **{cat.name}** ({file_count} files) - {cat.description}"
            )

        # Prepare uncategorized file list (shorter format to save tokens)
        uncategorized_summary = []
        for f in uncategorized:
            # Include first 500 chars of diff for context
            diff_preview = f.diff[:500] if f.diff else ""
            uncategorized_summary.append(
                {
                    "path": f.path,
                    "additions": f.additions,
                    "deletions": f.deletions,
                    "diff_preview": diff_preview,
                }
            )

        prompt = f"""These {len(uncategorized)} files were not categorized in the first pass.

EXISTING CATEGORIES:
{chr(10).join(existing_cat_summary)}

UNCATEGORIZED FILES:
{json.dumps(uncategorized_summary, indent=2)}

Your task:
1. Assign each uncategorized file to an existing category (use the category name)
2. OR create NEW categories if the files don't fit existing ones
3. Be generous - try to assign files rather than creating new categories

Return JSON in this format:
[
  {{
    "name": "Existing Category Name OR New Category Name",
    "description": "One sentence (only needed for NEW categories)",
    "is_new": false,
    "file_paths": ["path1", "path2"]
  }}
]

For existing categories, set is_new=false and omit description.
For new categories, set is_new=true and provide a description.
"""

        try:
            message = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )

            # Handle different content block types
            content_block = message.content[0]
            if hasattr(content_block, "text"):
                response_text = content_block.text.strip()
            else:
                response_text = str(content_block).strip()

            # Extract JSON from response
            if "```json" in response_text:
                response_text = (
                    response_text.split("```json")[1].split("```")[0].strip()
                )
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()

            second_pass_defs = json.loads(response_text)

            # Build file map for uncategorized files
            file_map = {f.path: f for f in uncategorized}

            # Process assignments
            for cat_def in second_pass_defs:
                cat_name = cat_def["name"]
                is_new = cat_def.get("is_new", False)
                assigned_files = [
                    file_map[path] for path in cat_def["file_paths"] if path in file_map
                ]

                if not assigned_files:
                    continue

                if is_new:
                    # Create new category
                    existing_categories.append(
                        Category(
                            name=cat_name,
                            description=cat_def.get(
                                "description", "Additional category from second pass"
                            ),
                            files=assigned_files,
                            priority=cat_def.get("priority", 5),
                            detailed_summary="",
                        )
                    )
                else:
                    # Add to existing category
                    for cat in existing_categories:
                        if cat.name == cat_name:
                            cat.files.extend(assigned_files)
                            break

            # Check if any files are still uncategorized after second pass
            all_categorized_paths = {
                f.path for cat in existing_categories for f in cat.files
            }
            still_uncategorized = [
                f for f in uncategorized if f.path not in all_categorized_paths
            ]

            if still_uncategorized:
                # Add remaining files to "Other"
                existing_categories.append(
                    Category(
                        name="Other",
                        description="Files not categorized after two passes",
                        files=still_uncategorized,
                        priority=10,
                    )
                )

            return existing_categories

        except Exception as e:
            print(f"  Warning: Second pass categorization failed: {e}", file=sys.stderr)
            # Add all uncategorized to "Other"
            existing_categories.append(
                Category(
                    name="Other",
                    description="Files not categorized by LLM analysis",
                    files=uncategorized,
                    priority=10,
                )
            )
            return existing_categories

    def generate_review(
        self, pr_info: dict[str, Any], categories: list[Category]
    ) -> str:
        """Generate comprehensive PR review summary"""

        # Prepare category summary for review context
        category_summary = []
        for cat in categories:
            category_summary.append(
                {
                    "name": cat.name,
                    "description": cat.description,
                    "file_count": len(cat.files),
                    "additions": sum(f.additions for f in cat.files),
                    "deletions": sum(f.deletions for f in cat.files),
                    "files": [f.path for f in cat.files[:5]],  # Sample files
                }
            )

        prompt = f"""You are reviewing a GitHub Pull Request. Provide a comprehensive review summary for this PR.

PR Title: {pr_info["title"]}
PR Description:
{pr_info.get("body", "No description")[:2000]}

Categories of Changes:
{json.dumps(category_summary, indent=2)}

Provide a comprehensive review in markdown format with the following sections:

## Overview
- High-level summary of what this PR accomplishes (2-3 sentences)
- Main goal/purpose of the changes

## Key Changes
- List the 3-5 most important changes
- Focus on what changed and why it matters

## Areas of Concern
- Potential issues, edge cases, or risks to watch for
- Breaking changes or backwards compatibility concerns
- Performance or security considerations

## Testing Recommendations
- What should be tested
- Edge cases to verify
- Integration points to check

Be specific and actionable. Reference actual changes when possible."""

        try:
            message = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )

            content_block = message.content[0]
            if hasattr(content_block, "text"):
                return content_block.text.strip()
            else:
                return str(content_block).strip()

        except Exception as e:
            print(f"  Warning: PR review generation failed: {e}", file=sys.stderr)
            return "**Review generation failed.** Unable to generate automated review summary."


class OpenAICategorizer:
    """Categorize files using OpenAI API"""

    def __init__(self, api_key: str):
        if not openai:
            raise ImportError("openai package not installed")
        if not httpx:
            raise ImportError("httpx package not installed")

        # SSL verification: Can be enabled by setting VERIFY_SSL=1 environment variable
        # Disabled by default as workaround for systems with Python SSL certificate issues
        verify_ssl = os.getenv("VERIFY_SSL") == "1"
        if not verify_ssl:
            print(
                "  ⚠️  WARNING: SSL verification disabled for OpenAI API",
                file=sys.stderr,
            )
            print(
                "      Set VERIFY_SSL=1 to enable (may require SSL certificate setup)",
                file=sys.stderr,
            )
        http_client = httpx.Client(verify=verify_ssl, timeout=60.0)
        self.client = openai.OpenAI(api_key=api_key, http_client=http_client)

    def categorize(
        self, pr_info: dict[str, Any], files: list[PRFile]
    ) -> list[Category]:
        """Categorize files using OpenAI analysis"""

        # Detect common patterns across all files
        patterns_summary = PatternDetector.detect_patterns(files)

        # Prepare file summary for LLM with more diff context
        file_summary = []
        for f in files:
            file_summary.append(
                {
                    "path": f.path,
                    "additions": f.additions,
                    "deletions": f.deletions,
                    "status": f.status,
                    "diff_preview": f.diff[:1000]
                    if f.diff
                    else "",  # First 1000 chars for better context
                }
            )

        prompt = f"""Analyze this GitHub Pull Request and categorize the changed files into logical groups.

CROSS-FILE PATTERNS DETECTED:
{patterns_summary}

Use these patterns to identify related changes that should be grouped together.
For example, if 20 files all add 'org_id', they likely belong in the same category.

---

Analyze this GitHub Pull Request and categorize the changed files into logical groups.

IMPORTANT: For each category, provide a detailed summary that will help reviewers understand:
1. What specifically changed in this category (be concrete, mention key functions/classes/patterns)
2. Why these changes were made (connect to PR description/goals)
3. What reviewers should pay attention to (edge cases, breaking changes, new patterns)
4. Any design decisions or architectural implications

Use the PR description and diffs to provide rich, actionable summaries.

PR Title: {pr_info["title"]}
PR Description:
{pr_info.get("body", "No description")[:1000]}

Changed Files ({len(files)} total):
{json.dumps(file_summary, indent=2)}

Please categorize these files into logical groups that would help a reviewer understand the PR structure. For each category:
1. Name it clearly (e.g., "Authentication & Sessions", "Database Schema", "API Routes")
2. Provide a brief description (one sentence)
3. Provide a detailed_summary (3-5 bullet points) that explains:
   - Specific changes made (mention key functions, classes, patterns)
   - Why these changes matter (connect to PR goals)
   - What reviewers should focus on (edge cases, breaking changes)
   - Design decisions or architectural implications
4. Assign a priority (1=highest, review first; 5=lowest, review last)
5. List which file paths belong to it

Focus on semantic grouping based on what changed, not just file paths. For example:
- If multiple services changed to add org_id, group as "Multi-tenancy Service Updates"
- If auth and session logic changed together, group as "Authentication System"
- Separate critical infrastructure changes from minor updates

Return ONLY a JSON array with this structure:
[
  {{
    "name": "Category Name",
    "description": "One-sentence summary",
    "detailed_summary": "**What Changed:**\\n- Bullet point 1\\n- Bullet point 2\\n\\n**Why It Matters:**\\n- Reason 1\\n\\n**Review Focus:**\\n- What to look for",
    "priority": 1,
    "file_paths": ["path/to/file1.py", "path/to/file2.py"]
  }}
]

Be concrete and actionable. Aim for 5-8 categories for a large PR."""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a code review assistant that categorizes PR changes.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=4096,
                temperature=0.3,
            )

            response_text = (response.choices[0].message.content or "").strip()

            # Extract JSON from response (handle markdown code blocks)
            if "```json" in response_text:
                response_text = (
                    response_text.split("```json")[1].split("```")[0].strip()
                )
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()

            category_defs = json.loads(response_text)

            # Build categories
            categories = []
            file_map = {f.path: f for f in files}

            for cat_def in category_defs:
                cat_files = [
                    file_map[path] for path in cat_def["file_paths"] if path in file_map
                ]
                if cat_files:
                    categories.append(
                        Category(
                            name=cat_def["name"],
                            description=cat_def["description"],
                            files=cat_files,
                            priority=cat_def.get("priority", 5),
                            detailed_summary=cat_def.get("detailed_summary", ""),
                        )
                    )

            # Check for uncategorized files and do a second pass
            categorized_paths = {f.path for cat in categories for f in cat.files}
            uncategorized = [f for f in files if f.path not in categorized_paths]

            if uncategorized and len(uncategorized) < len(files):
                # Second pass: Try to categorize remaining files
                print(
                    f"  Second pass: categorizing {len(uncategorized)} remaining files...",
                    file=sys.stderr,
                )
                categories = self._second_pass_categorization(
                    pr_info, uncategorized, categories
                )
            elif uncategorized:
                # All files are uncategorized - add to "Other"
                categories.append(
                    Category(
                        name="Other",
                        description="Files not categorized by LLM analysis",
                        files=uncategorized,
                        priority=10,
                    )
                )

            categories.sort(key=lambda c: (c.priority, c.name))
            return categories

        except Exception as e:
            print(f"Warning: OpenAI categorization failed: {e}", file=sys.stderr)
            print("Falling back to pattern-based categorization...", file=sys.stderr)
            return PatternCategorizer().categorize(files)

    def _second_pass_categorization(
        self,
        pr_info: dict[str, Any],
        uncategorized: list[PRFile],
        existing_categories: list[Category],
    ) -> list[Category]:
        """Second pass: categorize remaining files by assigning to existing or new categories"""

        # Build summary of existing categories
        existing_cat_summary = []
        for i, cat in enumerate(existing_categories):
            file_count = len(cat.files)
            existing_cat_summary.append(
                f"{i + 1}. **{cat.name}** ({file_count} files) - {cat.description}"
            )

        # Prepare uncategorized file list (shorter format to save tokens)
        uncategorized_summary = []
        for f in uncategorized:
            # Include first 500 chars of diff for context
            diff_preview = f.diff[:500] if f.diff else ""
            uncategorized_summary.append(
                {
                    "path": f.path,
                    "additions": f.additions,
                    "deletions": f.deletions,
                    "diff_preview": diff_preview,
                }
            )

        prompt = f"""These {len(uncategorized)} files were not categorized in the first pass.

EXISTING CATEGORIES:
{chr(10).join(existing_cat_summary)}

UNCATEGORIZED FILES:
{json.dumps(uncategorized_summary, indent=2)}

Your task:
1. Assign each uncategorized file to an existing category (use the category name)
2. OR create NEW categories if the files don't fit existing ones
3. Be generous - try to assign files rather than creating new categories

Return JSON in this format:
[
  {{
    "name": "Existing Category Name OR New Category Name",
    "description": "One sentence (only needed for NEW categories)",
    "is_new": false,
    "file_paths": ["path1", "path2"]
  }}
]

For existing categories, set is_new=false and omit description.
For new categories, set is_new=true and provide a description.
"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a code review assistant that categorizes PR changes.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=4096,
                temperature=0.3,
            )

            response_text = (response.choices[0].message.content or "").strip()

            # Extract JSON from response
            if "```json" in response_text:
                response_text = (
                    response_text.split("```json")[1].split("```")[0].strip()
                )
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()

            second_pass_defs = json.loads(response_text)

            # Build file map for uncategorized files
            file_map = {f.path: f for f in uncategorized}

            # Process assignments
            for cat_def in second_pass_defs:
                cat_name = cat_def["name"]
                is_new = cat_def.get("is_new", False)
                assigned_files = [
                    file_map[path] for path in cat_def["file_paths"] if path in file_map
                ]

                if not assigned_files:
                    continue

                if is_new:
                    # Create new category
                    existing_categories.append(
                        Category(
                            name=cat_name,
                            description=cat_def.get(
                                "description", "Additional category from second pass"
                            ),
                            files=assigned_files,
                            priority=cat_def.get("priority", 5),
                            detailed_summary="",
                        )
                    )
                else:
                    # Add to existing category
                    for cat in existing_categories:
                        if cat.name == cat_name:
                            cat.files.extend(assigned_files)
                            break

            # Check if any files are still uncategorized after second pass
            all_categorized_paths = {
                f.path for cat in existing_categories for f in cat.files
            }
            still_uncategorized = [
                f for f in uncategorized if f.path not in all_categorized_paths
            ]

            if still_uncategorized:
                # Add remaining files to "Other"
                existing_categories.append(
                    Category(
                        name="Other",
                        description="Files not categorized after two passes",
                        files=still_uncategorized,
                        priority=10,
                    )
                )

            return existing_categories

        except Exception as e:
            print(f"  Warning: Second pass categorization failed: {e}", file=sys.stderr)
            # Add all uncategorized to "Other"
            existing_categories.append(
                Category(
                    name="Other",
                    description="Files not categorized by LLM analysis",
                    files=uncategorized,
                    priority=10,
                )
            )
            return existing_categories

    def generate_review(
        self, pr_info: dict[str, Any], categories: list[Category]
    ) -> str:
        """Generate comprehensive PR review summary"""

        # Prepare category summary for review context
        category_summary = []
        for cat in categories:
            category_summary.append(
                {
                    "name": cat.name,
                    "description": cat.description,
                    "file_count": len(cat.files),
                    "additions": sum(f.additions for f in cat.files),
                    "deletions": sum(f.deletions for f in cat.files),
                    "files": [f.path for f in cat.files[:5]],  # Sample files
                }
            )

        prompt = f"""You are reviewing a GitHub Pull Request. Provide a comprehensive review summary for this PR.

PR Title: {pr_info["title"]}
PR Description:
{pr_info.get("body", "No description")[:2000]}

Categories of Changes:
{json.dumps(category_summary, indent=2)}

Provide a comprehensive review in markdown format with the following sections:

## Overview
- High-level summary of what this PR accomplishes (2-3 sentences)
- Main goal/purpose of the changes

## Key Changes
- List the 3-5 most important changes
- Focus on what changed and why it matters

## Areas of Concern
- Potential issues, edge cases, or risks to watch for
- Breaking changes or backwards compatibility concerns
- Performance or security considerations

## Testing Recommendations
- What should be tested
- Edge cases to verify
- Integration points to check

Be specific and actionable. Reference actual changes when possible."""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a thorough code reviewer providing actionable PR reviews.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=2048,
                temperature=0.3,
            )

            return (response.choices[0].message.content or "").strip()

        except Exception as e:
            print(f"  Warning: PR review generation failed: {e}", file=sys.stderr)
            return "**Review generation failed.** Unable to generate automated review summary."
