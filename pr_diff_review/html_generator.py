import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from pr_diff_review.models import PRFile, Category
from pr_diff_review.ast_comparer import ASTComparer

if TYPE_CHECKING:
    from pr_diff_review.fetcher import PRDiffFetcher


class HTMLGenerator:
    """Generate HTML diff viewer"""

    def __init__(
        self,
        link_mode: str = "diff",
        head_sha: str | None = None,
        repo: str | None = None,
        embed_assets: bool = False,
        existing_comments: dict | None = None,
        file_fetcher: Optional["PRDiffFetcher"] = None,
    ):
        """
        Args:
            link_mode: "diff" for PR line anchors (works on small PRs, allows commenting)
                      "file" for PR file anchors (always work, allows commenting)
                      "blob" for direct blob line links (always work, but can't comment)
            head_sha: Head commit SHA (required for blob mode)
            repo: Repository name (required for blob mode)
            embed_assets: If True, inline CSS/JS (offline mode).
                         If False, link to /static/ files (server mode).
            existing_comments: Dict of existing comments keyed by "path:line:side"
            file_fetcher: PRDiffFetcher instance for context expansion (optional)
        """
        self.link_mode = link_mode
        self.head_sha = head_sha
        self.repo = repo
        self.embed_assets = embed_assets
        self.existing_comments = existing_comments or {}
        self.file_fetcher = file_fetcher
        self.ast_comparer = ASTComparer(file_fetcher)

    def generate(
        self,
        pr_info: dict[str, Any],
        categories: list[Category],
        output_path: Path,
        diff_hashes: dict[str, str] | None = None,
        pr_review: str | None = None,
    ) -> None:
        """Generate HTML file"""

        html = self._build_html(pr_info, categories, diff_hashes or {}, pr_review)
        output_path.write_text(html, encoding="utf-8")
        print(f"✓ Generated: {output_path}")

    def _build_html(
        self,
        pr_info: dict[str, Any],
        categories: list[Category],
        diff_hashes: dict[str, str],
        pr_review: str | None = None,
    ) -> str:
        """Build complete HTML document"""

        # Calculate total stats
        total_additions = sum(f.additions for cat in categories for f in cat.files)
        total_deletions = sum(f.deletions for cat in categories for f in cat.files)
        total_files = sum(len(cat.files) for cat in categories)

        # Generate category sections
        category_html = []
        for i, category in enumerate(categories):
            cat_additions = sum(f.additions for f in category.files)
            cat_deletions = sum(f.deletions for f in category.files)

            files_html = []
            for file_idx, file in enumerate(category.files):
                file_id = f"cat{i}-file{file_idx}"
                file_html = self._format_file_diff(
                    file, file_id, pr_info["url"], diff_hashes
                )
                files_html.append(file_html)

            priority_badge = f'<span class="priority priority-{category.priority}">P{category.priority}</span>'

            # Add detailed summary section if available
            summary_html = ""
            if category.detailed_summary:
                # Convert markdown-style formatting to HTML
                summary_text = category.detailed_summary
                # Handle newlines (both literal \n and escaped \\n)
                summary_text = summary_text.replace("\\n", "\n").replace("\n", "<br>\n")
                # Handle bold **text**
                import re

                summary_text = re.sub(
                    r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", summary_text
                )
                # Handle bullet points with proper list formatting
                lines = summary_text.split("<br>")
                formatted_lines = []
                in_list = False
                for line in lines:
                    stripped = line.strip()
                    if stripped.startswith("- "):
                        if not in_list:
                            formatted_lines.append("<ul>")
                            in_list = True
                        formatted_lines.append(f"<li>{stripped[2:]}</li>")
                    else:
                        if in_list:
                            formatted_lines.append("</ul>")
                            in_list = False
                        if stripped:
                            formatted_lines.append(f"<p>{stripped}</p>")
                if in_list:
                    formatted_lines.append("</ul>")
                summary_formatted = "\n".join(formatted_lines)

                summary_html = f"""
                <div class="category-summary" id="summary-{i}">
                    <button class="summary-toggle" onclick="event.stopPropagation(); toggleSummary({i})">
                        <span class="toggle-arrow" id="summary-arrow-{i}">▼</span>
                        <span>Hide detailed analysis</span>
                    </button>
                    <div class="summary-content" id="summary-content-{i}">
                        {summary_formatted}
                    </div>
                </div>
                """

            category_html.append(f"""
            <div class="category" id="category-{i}">
                <div class="category-header" onclick="toggleCategory({i})">
                    <h2>
                        <span class="toggle-icon" id="toggle-{i}">▼</span>
                        {category.name}
                        {priority_badge}
                        <span class="category-stats">
                            {len(category.files)} files
                            <span class="additions">+{cat_additions}</span>
                            <span class="deletions">-{cat_deletions}</span>
                        </span>
                    </h2>
                    <p class="category-description">{category.description}</p>
                </div>
                {summary_html}
                <div class="category-content" id="content-{i}">
                    {"".join(files_html)}
                </div>
            </div>
            """)

        # Add data attributes to categories for JS tracking
        category_html_with_data = []
        for i, html_content in enumerate(category_html):
            cat = categories[i]
            # Inject data attributes with escaped category name to prevent XSS
            import html as html_module

            escaped_cat_name = html_module.escape(cat.name, quote=True)
            html_with_data = html_content.replace(
                f'<div class="category" id="category-{i}">',
                f'<div class="category" id="category-{i}" data-category-name="{escaped_cat_name}">',
            )
            category_html_with_data.append(html_with_data)

        # Determine asset inclusion method
        if self.embed_assets:
            # Include Prism.js CSS and JS from CDN for syntax highlighting
            prism_css = '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/themes/prism-tomorrow.min.css">'
            prism_js = """
    <script>
        // Disable Prism's automatic highlighting - we'll do it manually
        window.Prism = window.Prism || {};
        Prism.manual = true;
    </script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/prism.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-python.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-typescript.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-javascript.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-json.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-yaml.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-java.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-cpp.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-c.min.js"></script>"""
            css = f"{prism_css}\n<style>{self._get_css()}</style>"
            js_section = f"{prism_js}\n<script>{self._get_javascript()}</script>"
            comment_ui = ""  # No comment UI in offline mode
            header_actions = ""  # No comment button in offline mode
        else:
            import time

            cache_bust = int(time.time())
            # Include Prism.js CSS and JS from CDN for syntax highlighting
            prism_css = '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/themes/prism-tomorrow.min.css">'
            prism_js = """
    <script>
        // Disable Prism's automatic highlighting - we'll do it manually
        window.Prism = window.Prism || {};
        Prism.manual = true;
    </script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/prism.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-python.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-typescript.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-javascript.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-json.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-yaml.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-java.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-cpp.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-c.min.js"></script>"""
            css = f'{prism_css}\n<link rel="stylesheet" href="/static/pr-diff-viewer.css?v={cache_bust}">'
            # Comment UI and metadata for server mode
            comment_ui = f"""
    <!-- Comment form overlay -->
    <div class="comment-form-overlay" id="comment-overlay" style="display:none">
        <div class="comment-form-container">
            <h3 id="comment-form-title">Add Comment</h3>
            <div class="comment-context" id="comment-context" style="display:none">
                <code id="comment-location"></code>
            </div>
            <textarea id="comment-body" placeholder="Write your comment (supports markdown)..."></textarea>
            <div class="comment-actions">
                <button onclick="submitComment()" class="btn-primary">Post Comment</button>
                <button onclick="hideCommentForm()" class="btn-secondary">Cancel</button>
            </div>
            <div id="comment-status"></div>
        </div>
    </div>

    <!-- PR metadata for comment API -->
    <script>
        window.PR_REPO = '{self.repo}';
        window.PR_NUMBER = {pr_info["number"]};
        window.COMMIT_SHA = '{self.head_sha}';
    </script>

    {prism_js}
    <!-- External JavaScript -->
    <script src="/static/pr-diff-viewer.js?v={cache_bust}"></script>"""
            js_section = comment_ui
            header_actions = """<button class="general-comment-btn" onclick="showGeneralCommentForm()" title="Add PR comment">
                    💬 Comment on PR
                </button>
                """

        # Escape user-provided content to prevent XSS
        import html as html_module

        escaped_title = html_module.escape(pr_info["title"])
        escaped_author = html_module.escape(pr_info["author"]["login"])
        escaped_url = html_module.escape(pr_info["url"], quote=True)

        # Generate category navigation for sidebar
        category_nav_items = []
        for i, category in enumerate(categories):
            cat_additions = sum(f.additions for f in category.files)
            cat_deletions = sum(f.deletions for f in category.files)
            priority_badge = f'<span class="priority priority-{category.priority}">P{category.priority}</span>'

            category_nav_items.append(f"""
            <div class="category-nav-item" data-category-id="{i}" onclick="scrollToCategory({i})">
                <div class="category-nav-header">
                    <span class="category-nav-name">{category.name}</span>
                    {priority_badge}
                </div>
                <div class="category-nav-stats">
                    <span class="file-count">{len(category.files)} files</span>
                    <span class="additions">+{cat_additions}</span>
                    <span class="deletions">-{cat_deletions}</span>
                </div>
            </div>
            """)

        # Generate PR review section
        if pr_review:
            # Convert markdown to HTML (enhanced conversion)
            import html as html_module
            import re

            review_html = pr_review

            # Convert inline code first (before other formatting)
            review_html = re.sub(r"`([^`]+)`", r"<code>\1</code>", review_html)

            # Convert headers
            review_html = re.sub(
                r"^### (.+)$", r"<h4>\1</h4>", review_html, flags=re.MULTILINE
            )
            review_html = re.sub(
                r"^## (.+)$", r"<h3>\1</h3>", review_html, flags=re.MULTILINE
            )
            review_html = re.sub(
                r"^# (.+)$", r"<h2>\1</h2>", review_html, flags=re.MULTILINE
            )

            # Convert bold (must come before italic)
            review_html = re.sub(
                r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", review_html
            )

            # Convert italic (single asterisks not in strong tags)
            review_html = re.sub(
                r"(?<!<strong>)\*([^*]+)\*(?!</strong>)", r"<em>\1</em>", review_html
            )

            # Process line by line for lists and paragraphs
            lines = review_html.split("\n")
            formatted_lines = []
            in_bullet_list = False
            in_numbered_list = False

            for line in lines:
                stripped = line.strip()

                # Bullet list items
                if stripped.startswith("- "):
                    if in_numbered_list:
                        formatted_lines.append("</ol>")
                        in_numbered_list = False
                    if not in_bullet_list:
                        formatted_lines.append("<ul>")
                        in_bullet_list = True
                    formatted_lines.append(f"<li>{stripped[2:]}</li>")

                # Numbered list items
                elif re.match(r"^\d+\.\s+", stripped):
                    if in_bullet_list:
                        formatted_lines.append("</ul>")
                        in_bullet_list = False
                    if not in_numbered_list:
                        formatted_lines.append("<ol>")
                        in_numbered_list = True
                    content = re.sub(r"^\d+\.\s+", "", stripped)
                    formatted_lines.append(f"<li>{content}</li>")

                # Close lists and handle regular content
                else:
                    if in_bullet_list:
                        formatted_lines.append("</ul>")
                        in_bullet_list = False
                    if in_numbered_list:
                        formatted_lines.append("</ol>")
                        in_numbered_list = False

                    if stripped:
                        # Don't wrap headers in <p> tags
                        if not stripped.startswith("<h"):
                            formatted_lines.append(f"<p>{stripped}</p>")
                        else:
                            formatted_lines.append(stripped)

            # Close any open lists
            if in_bullet_list:
                formatted_lines.append("</ul>")
            if in_numbered_list:
                formatted_lines.append("</ol>")

            review_html = "\n".join(formatted_lines)

            pr_review_section = f"""
    <div class="pr-review-section collapsed" id="pr-review">
        <button class="pr-review-toggle" onclick="togglePRReview()">
            <span class="toggle-arrow" id="pr-review-arrow">▶</span>
            <span class="pr-review-title">PR Review Summary</span>
        </button>
        <div class="pr-review-content" id="pr-review-content">
            {review_html}
        </div>
    </div>
    """
        else:
            pr_review_section = ""

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PR #{pr_info["number"]}: {escaped_title}</title>
    {css}
</head>
<body>
    <div class="header">
        <div class="header-top">
            <h1>PR #{pr_info["number"]}: {escaped_title}</h1>
            <div class="header-actions">
                {header_actions}
                <label class="formatting-toggle">
                    <input type="checkbox" id="formatting-toggle-checkbox" onchange="toggleFormatting()" checked>
                    <span>Hide formatting changes</span>
                </label>
                <label class="theme-toggle">
                    <input type="checkbox" id="theme-toggle-checkbox" onchange="toggleTheme()">
                    <span>Light mode</span>
                </label>
            </div>
        </div>
        <div class="pr-meta">
            <span class="author">by {escaped_author}</span>
            <a href="{escaped_url}" target="github-pr" class="pr-link">View on GitHub →</a>
        </div>
        <div class="pr-stats">
            <span class="stat">{total_files} files changed</span>
            <span class="stat additions">+{total_additions} additions</span>
            <span class="stat deletions">-{total_deletions} deletions</span>
        </div>
    </div>

    {pr_review_section}

    <div class="main-content">
        <div class="categories-sidebar">
            <div class="categories-nav">
                {"".join(category_nav_items)}
            </div>
        </div>
        <div class="files-content" id="files-content">
            {"".join(category_html_with_data)}
        </div>
    </div>

    {js_section}
</body>
</html>"""

    def _get_language_class(self, file_path: str) -> str:
        """Get Prism.js language class from file extension"""
        extension = Path(file_path).suffix.lower()
        language_map = {
            ".py": "python",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".js": "javascript",
            ".jsx": "javascript",
            ".json": "json",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".java": "java",
            ".cpp": "cpp",
            ".cc": "cpp",
            ".cxx": "cpp",
            ".c": "c",
            ".h": "c",
            ".hpp": "cpp",
        }
        return language_map.get(extension, "")

    def _format_file_diff(
        self, file: PRFile, file_id: str, pr_url: str, diff_hashes: dict[str, str]
    ) -> str:
        """Format a single file's diff"""
        status_class = {
            "added": "file-added",
            "removed": "file-removed",
            "modified": "file-modified",
            "renamed": "file-renamed",
        }.get(file.status, "file-modified")

        status_icon = {
            "added": "+",
            "removed": "-",
            "modified": "M",
            "renamed": "R",
        }.get(file.status, "M")

        # Get language for syntax highlighting
        language = self._get_language_class(file.path)

        # Format diff with custom coloring (avoid Pygments inline styles)
        if file.diff:
            highlighted, has_non_formatting_changes = self._colorize_diff(
                file.diff, file.path, pr_url, diff_hashes, language
            )
            highlighted = highlighted.replace("{file_id}", file_id)
        else:
            highlighted = '<pre class="diff-content">No diff available</pre>'
            has_non_formatting_changes = True  # No diff means no formatting-only file

        # Add class for files with only formatting changes
        formatting_only_class = "" if has_non_formatting_changes else " formatting-only"

        # Escape file path for JavaScript string
        import json

        escaped_path = json.dumps(file.path)

        return f"""
        <div class="file {status_class}{formatting_only_class}" data-file-path="{file.path}" data-language="{language}">
            <div class="file-header" onclick="toggleFile('{file_id}')">
                <span class="toggle-icon" id="toggle-{file_id}">▼</span>
                <span class="file-status">{status_icon}</span>
                <span class="file-path" onclick="copyFilePath({escaped_path}, event)" title="Click to copy path">{file.path}</span>
                <span class="file-stats">
                    <span class="additions">+{file.additions}</span>
                    <span class="deletions">-{file.deletions}</span>
                </span>
            </div>
            <div class="file-diff" id="diff-{file_id}">
                {highlighted}
            </div>
        </div>
        """

    def _get_existing_comment_indicator(
        self, file_path: str, line: int, side: str
    ) -> str:
        """Get HTML for existing comment indicator if comments exist for this line"""
        key = f"{file_path}:{line}:{side}"
        comments = self.existing_comments.get(key, [])

        if not comments:
            return ""

        # Use the first comment's URL (GitHub groups them)
        html_url = comments[0]["html_url"]
        count = len(comments)
        title = f"{count} comment{'s' if count > 1 else ''}"

        return f'<a href="{html_url}" target="github-pr" class="comment-indicator" title="{title}">💬</a>'

    def _colorize_diff(
        self,
        diff: str,
        file_path: str,
        pr_url: str,
        diff_hashes: dict[str, str],
        language: str = "",
    ) -> tuple[str, bool]:
        """Colorize diff lines with CSS classes, line numbers, inline change markers, and syntax highlighting

        Returns:
            Tuple of (html_string, has_non_formatting_changes)
        """
        import html
        import re

        lines = diff.split("\n")
        has_non_formatting_changes = False  # Track if file has substantive changes

        # Get GitHub's actual diff hash for this file
        diff_hash = diff_hashes.get(file_path, "unknown")
        github_files_url = f"{pr_url}/files"

        # Separate meta lines from actual diff
        meta_lines = []
        diff_lines = []
        in_meta = True

        for line in lines:
            if in_meta and (
                line.startswith("diff --git")
                or line.startswith("index ")
                or line.startswith("+++")
                or line.startswith("---")
            ):
                meta_lines.append(line)
            else:
                in_meta = False
                diff_lines.append(line)

        # Build collapsible meta section
        meta_html = ""
        if meta_lines:
            meta_content = "\n".join(html.escape(line) for line in meta_lines)
            meta_html = f"""
            <div class="diff-meta-section collapsed" id="meta-{{file_id}}">
                <button class="diff-meta-toggle" onclick="toggleMeta('{{file_id}}')">
                    <span class="toggle-arrow">▶</span> Show diff command
                </button>
                <pre class="diff-meta-content">{meta_content}</pre>
            </div>
            """

        # Parse hunks and track line numbers
        old_line = 0
        new_line = 0
        colored_lines = []

        def make_line_link(line_num: int, side: str) -> str:
            """Generate GitHub link for a line number"""
            if line_num == 0:
                return ""

            if self.link_mode == "blob" and side == "R" and self.head_sha and self.repo:
                # Use blob view for new lines (always works, even on large PRs)
                blob_url = f"https://github.com/{self.repo}/blob/{self.head_sha}/{file_path}#L{line_num}"
                return blob_url
            elif self.link_mode == "blob":
                # Can't link old lines in blob mode
                return ""
            elif self.link_mode == "file":
                # Link to file in PR (always works), user scrolls to find line
                return f"{github_files_url}#diff-{diff_hash}"
            else:
                # Use diff anchors (may not work on large PRs due to lazy loading)
                anchor = f"diff-{diff_hash}{side}{line_num}"
                return f"{github_files_url}#{anchor}"

        # Track consecutive del/add lines for pairing
        i = 0
        while i < len(diff_lines):
            line = diff_lines[i]

            # Parse hunk header to get line numbers
            if line.startswith("@@"):
                match = re.match(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
                if match:
                    old_line = int(match.group(1))
                    new_line = int(match.group(2))
                escaped = html.escape(line)
                colored_lines.append(
                    f'<tr><td class="line-num old-num"></td><td class="line-num new-num"></td><td class="comment-btn-col"></td><td class="line-content"><span class="diff-hunk">{escaped}</span></td></tr>'
                )
                i += 1
            elif line.startswith("-") and not line.startswith("---"):
                # Look ahead for matching + lines to pair for word-level diff
                del_lines = []
                add_lines = []
                j = i

                # Collect consecutive - lines
                while (
                    j < len(diff_lines)
                    and diff_lines[j].startswith("-")
                    and not diff_lines[j].startswith("---")
                ):
                    del_lines.append(diff_lines[j][1:])
                    j += 1

                # Collect consecutive + lines
                while (
                    j < len(diff_lines)
                    and diff_lines[j].startswith("+")
                    and not diff_lines[j].startswith("+++")
                ):
                    add_lines.append(diff_lines[j][1:])
                    j += 1

                # Detect formatting-only changes using AST comparison
                is_formatting_change = False
                if del_lines and add_lines:
                    # Join lines to form complete code blocks for AST parsing
                    del_code = "\n".join(del_lines)
                    add_code = "\n".join(add_lines)

                    # Try AST comparison first (more accurate)
                    # Pass line numbers for potential context expansion
                    is_formatting_change = self.ast_comparer.are_semantically_equal(
                        del_code, add_code, file_path, old_line, new_line
                    )

                # Track if there are non-formatting changes
                if not is_formatting_change:
                    has_non_formatting_changes = True

                formatting_class = " formatting-change" if is_formatting_change else ""

                # Output deletion lines with word-level highlighting only if paired with similar addition
                for idx, del_text in enumerate(del_lines):
                    escaped = html.escape(del_text)
                    # Pair with corresponding add line if available AND similar enough
                    pair_text = add_lines[idx] if idx < len(add_lines) else None
                    if pair_text and self._is_similar_enough(del_text, pair_text):
                        escaped_pair = html.escape(pair_text)
                        highlighted = self._highlight_inline_changes(
                            escaped, "del", escaped_pair
                        )
                    else:
                        # No word-level diff for unmatched or dissimilar lines
                        highlighted = f'<span class="diff-del">{escaped}</span>'

                    # Add comment button for deleted lines (only in server mode)
                    if not self.embed_assets:
                        comment_btn_cell = '<td class="comment-btn-col"><button class="comment-btn" onclick="showCommentForm(this, event)" title="Add comment"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M1 2.75C1 1.784 1.784 1 2.75 1h10.5c.966 0 1.75.784 1.75 1.75v7.5A1.75 1.75 0 0113.25 12H9.06l-2.573 2.573A1.458 1.458 0 014 13.543V12H2.75A1.75 1.75 0 011 10.25Zm1.75-.25a.25.25 0 00-.25.25v7.5c0 .138.112.25.25.25h2a.75.75 0 01.75.75v2.19l2.72-2.72a.75.75 0 01.53-.22h4.5a.25.25 0 00.25-.25v-7.5a.25.25 0 00-.25-.25Z"></path></svg></button></td>'
                        existing_indicator = self._get_existing_comment_indicator(
                            file_path, old_line, "LEFT"
                        )
                    else:
                        comment_btn_cell = '<td class="comment-btn-col"></td>'
                        existing_indicator = ""

                    old_link = make_line_link(old_line, "L")
                    old_num_html = (
                        f'<a href="{old_link}" target="github-pr">{old_line}</a>{existing_indicator}'
                        if old_link
                        else f"{old_line}{existing_indicator}"
                    )
                    colored_lines.append(
                        f'<tr class="diff-line-del{formatting_class}" data-file-path="{file_path}" data-line="{old_line}" data-side="LEFT"><td class="line-num old-num">{old_num_html}</td><td class="line-num new-num"></td>{comment_btn_cell}<td class="line-content">{highlighted}</td></tr>'
                    )
                    old_line += 1

                # Output addition lines with word-level highlighting only if paired with similar deletion
                for idx, add_text in enumerate(add_lines):
                    escaped = html.escape(add_text)
                    # Pair with corresponding del line if available AND similar enough
                    pair_text = del_lines[idx] if idx < len(del_lines) else None
                    has_pair = pair_text and self._is_similar_enough(
                        add_text, pair_text
                    )
                    if has_pair:
                        assert pair_text is not None  # has_pair guarantees this
                        escaped_pair = html.escape(pair_text)
                        highlighted = self._highlight_inline_changes(
                            escaped, "add", escaped_pair
                        )
                    else:
                        # No word-level diff for unmatched or dissimilar lines
                        highlighted = f'<span class="diff-add">{escaped}</span>'

                    # Add comment button for added/modified lines (only in server mode)
                    if not self.embed_assets:
                        comment_btn_cell = '<td class="comment-btn-col"><button class="comment-btn" onclick="showCommentForm(this, event)" title="Add comment"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M1 2.75C1 1.784 1.784 1 2.75 1h10.5c.966 0 1.75.784 1.75 1.75v7.5A1.75 1.75 0 0113.25 12H9.06l-2.573 2.573A1.458 1.458 0 014 13.543V12H2.75A1.75 1.75 0 011 10.25Zm1.75-.25a.25.25 0 00-.25.25v7.5c0 .138.112.25.25.25h2a.75.75 0 01.75.75v2.19l2.72-2.72a.75.75 0 01.53-.22h4.5a.25.25 0 00.25-.25v-7.5a.25.25 0 00-.25-.25Z"></path></svg></button></td>'
                        existing_indicator = self._get_existing_comment_indicator(
                            file_path, new_line, "RIGHT"
                        )
                    else:
                        comment_btn_cell = '<td class="comment-btn-col"></td>'
                        existing_indicator = ""

                    new_link = make_line_link(new_line, "R")
                    new_num_html = f'<a href="{new_link}" target="github-pr">{new_line}</a>{existing_indicator}'
                    colored_lines.append(
                        f'<tr class="diff-line-add{formatting_class}" data-file-path="{file_path}" data-line="{new_line}" data-side="RIGHT"><td class="line-num old-num"></td><td class="line-num new-num">{new_num_html}</td>{comment_btn_cell}<td class="line-content">{highlighted}</td></tr>'
                    )
                    new_line += 1

                i = j
            elif line.startswith("+") and not line.startswith("+++"):
                # Standalone + line (not paired with -)
                has_non_formatting_changes = True
                escaped = html.escape(line[1:])
                highlighted = self._highlight_inline_changes(escaped, "add")

                # Add comment button for added lines (only in server mode)
                if not self.embed_assets:
                    comment_btn_cell = '<td class="comment-btn-col"><button class="comment-btn" onclick="showCommentForm(this, event)" title="Add comment"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M1 2.75C1 1.784 1.784 1 2.75 1h10.5c.966 0 1.75.784 1.75 1.75v7.5A1.75 1.75 0 0113.25 12H9.06l-2.573 2.573A1.458 1.458 0 014 13.543V12H2.75A1.75 1.75 0 011 10.25Zm1.75-.25a.25.25 0 00-.25.25v7.5c0 .138.112.25.25.25h2a.75.75 0 01.75.75v2.19l2.72-2.72a.75.75 0 01.53-.22h4.5a.25.25 0 00.25-.25v-7.5a.25.25 0 00-.25-.25Z"></path></svg></button></td>'
                    existing_indicator = self._get_existing_comment_indicator(
                        file_path, new_line, "RIGHT"
                    )
                else:
                    comment_btn_cell = '<td class="comment-btn-col"></td>'
                    existing_indicator = ""

                new_link = make_line_link(new_line, "R")
                new_num_html = f'<a href="{new_link}" target="github-pr">{new_line}</a>{existing_indicator}'
                colored_lines.append(
                    f'<tr class="diff-line-add" data-file-path="{file_path}" data-line="{new_line}" data-side="RIGHT"><td class="line-num old-num"></td><td class="line-num new-num">{new_num_html}</td>{comment_btn_cell}<td class="line-content">{highlighted}</td></tr>'
                )
                new_line += 1
                i += 1
            elif line.strip():  # Context line (not empty)
                escaped = html.escape(line[1:] if line.startswith(" ") else line)
                old_link = make_line_link(old_line, "L")
                new_link = make_line_link(new_line, "R")

                # Add comment button for context lines (only in server mode)
                if not self.embed_assets:
                    comment_btn_cell = '<td class="comment-btn-col"><button class="comment-btn" onclick="showCommentForm(this, event)" title="Add comment"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M1 2.75C1 1.784 1.784 1 2.75 1h10.5c.966 0 1.75.784 1.75 1.75v7.5A1.75 1.75 0 0113.25 12H9.06l-2.573 2.573A1.458 1.458 0 014 13.543V12H2.75A1.75 1.75 0 011 10.25Zm1.75-.25a.25.25 0 00-.25.25v7.5c0 .138.112.25.25.25h2a.75.75 0 01.75.75v2.19l2.72-2.72a.75.75 0 01.53-.22h4.5a.25.25 0 00.25-.25v-7.5a.25.25 0 00-.25-.25Z"></path></svg></button></td>'
                    existing_indicator = self._get_existing_comment_indicator(
                        file_path, new_line, "RIGHT"
                    )
                else:
                    comment_btn_cell = '<td class="comment-btn-col"></td>'
                    existing_indicator = ""

                old_num_html = (
                    f'<a href="{old_link}" target="github-pr">{old_line}</a>'
                    if old_link
                    else f"{old_line}"
                )
                new_num_html = (
                    f'<a href="{new_link}" target="github-pr">{new_line}</a>{existing_indicator}'
                    if new_link
                    else f"{new_line}{existing_indicator}"
                )

                colored_lines.append(
                    f'<tr data-file-path="{file_path}" data-line="{new_line}" data-side="RIGHT"><td class="line-num old-num">{old_num_html}</td><td class="line-num new-num">{new_num_html}</td>{comment_btn_cell}<td class="line-content"><span class="diff-ctx">{escaped}</span></td></tr>'
                )
                old_line += 1
                new_line += 1
                i += 1
            else:
                # Empty line
                colored_lines.append(
                    '<tr><td class="line-num old-num"></td><td class="line-num new-num"></td><td class="comment-btn-col"></td><td class="line-content"><span class="diff-ctx"></span></td></tr>'
                )
                i += 1

        # Add language class for syntax highlighting
        lang_class = f" language-{language}" if language else ""
        table_html = (
            f'<table class="diff-table{lang_class}">'
            + "\n".join(colored_lines)
            + "</table>"
        )
        return meta_html + table_html, has_non_formatting_changes

    def _is_similar_enough(
        self, text1: str, text2: str, threshold: float = 0.8
    ) -> bool:
        """Check if two lines are similar enough to warrant inline diffing"""
        import difflib

        # GitHub-like heuristics for inline highlighting
        ratio = difflib.SequenceMatcher(None, text1, text2).ratio()
        if ratio < threshold:
            return False

        # Skip if length difference is too large (>50%)
        len1, len2 = len(text1), len(text2)
        if len1 == 0 or len2 == 0:
            return False
        length_ratio = min(len1, len2) / max(len1, len2)
        if length_ratio < 0.5:
            return False

        return True

    def _highlight_inline_changes(
        self, text: str, change_type: str, pair_text: str | None = None
    ) -> str:
        """Add inline change highlighting with character-level diffing (preserves whitespace)"""
        css_class = "diff-add" if change_type == "add" else "diff-del"

        # If no pair text provided, just return basic highlighting
        if not pair_text:
            return f'<span class="{css_class}">{text}</span>'

        # Perform character-level diff to preserve all whitespace including indentation
        import difflib

        # Determine which text is which based on change type
        text1 = text if change_type == "del" else pair_text
        text2 = pair_text if change_type == "del" else text

        # Use SequenceMatcher at character level
        matcher = difflib.SequenceMatcher(None, text1, text2)
        result = []

        # Track which characters in our text are changed
        changed_positions: set[int] = set()
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag in ("replace", "delete", "insert"):
                if change_type == "del":
                    changed_positions.update(range(i1, i2))
                else:  # "add"
                    changed_positions.update(range(j1, j2))

        # Build result with <mark> tags around changed character sequences
        # Note: text is already HTML-escaped by caller, so we don't escape again
        i = 0
        while i < len(text):
            if i in changed_positions:
                # Start of changed sequence - collect all consecutive changed chars
                mark_start = i
                while i < len(text) and i in changed_positions:
                    i += 1
                # Wrap changed text in <mark> (already escaped by caller)
                result.append(f"<mark>{text[mark_start:i]}</mark>")
            else:
                # Unchanged character sequence - just add as-is
                unchanged_start = i
                while i < len(text) and i not in changed_positions:
                    i += 1
                result.append(text[unchanged_start:i])

        highlighted_text = "".join(result)
        return f'<span class="{css_class}">{highlighted_text}</span>'

    def _get_css(self) -> str:
        """Return embedded CSS with Prism theme"""
        # Read main CSS file
        main_css_path = Path(__file__).parent / "static" / "pr-diff-viewer.css"
        if main_css_path.exists():
            main_css = main_css_path.read_text(encoding="utf-8")
            # Remove @import statement since we'll include Prism theme separately
            main_css = main_css.replace("@import url('prism-github-theme.css');", "")

            # Read Prism theme CSS
            prism_theme_path = (
                Path(__file__).parent / "static" / "prism-github-theme.css"
            )
            prism_theme = ""
            if prism_theme_path.exists():
                prism_theme = prism_theme_path.read_text(encoding="utf-8")

            return prism_theme + "\n" + main_css

        # Fallback to inline CSS if file not found
        return """
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
            background: #0d1117;
            color: #c9d1d9;
            line-height: 1.5;
            overflow-y: scroll;
            transition: background-color 0.3s ease, color 0.3s ease;
        }

        body.light-mode {
            background: #ffffff;
            color: #24292f;
        }

        .header {
            background: #161b22;
            border-bottom: 1px solid #30363d;
            padding: 24px;
            position: sticky;
            top: 0;
            z-index: 1000;
            transition: background-color 0.3s ease, border-color 0.3s ease;
        }

        body.light-mode .header {
            background: #f6f8fa;
            border-bottom: 1px solid #d0d7de;
        }

        .header-top {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }

        .header h1 {
            font-size: 24px;
            font-weight: 600;
            color: #f0f6fc;
            margin: 0;
        }

        body.light-mode .header h1 {
            color: #24292f;
        }

        .theme-toggle, .formatting-toggle {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 14px;
            cursor: pointer;
            user-select: none;
        }

        .theme-toggle input[type="checkbox"], .formatting-toggle input[type="checkbox"] {
            cursor: pointer;
        }

        .theme-toggle span, .formatting-toggle span {
            color: #8b949e;
        }

        body.light-mode .theme-toggle span, body.light-mode .formatting-toggle span {
            color: #57606a;
        }

        /* Hide formatting changes when checkbox is checked */
        body.hide-formatting .formatting-change {
            display: none;
        }

        .pr-meta {
            display: flex;
            gap: 16px;
            align-items: center;
            margin-bottom: 12px;
            font-size: 14px;
        }

        .author {
            color: #8b949e;
        }

        body.light-mode .author {
            color: #57606a;
        }

        .pr-link {
            color: #58a6ff;
            text-decoration: none;
        }

        body.light-mode .pr-link {
            color: #0969da;
        }

        .pr-link:hover {
            text-decoration: underline;
        }

        .pr-stats {
            display: flex;
            gap: 16px;
            font-size: 14px;
        }

        .stat {
            color: #8b949e;
        }

        body.light-mode .stat {
            color: #57606a;
        }

        .additions {
            color: #3fb950;
        }

        .deletions {
            color: #f85149;
        }

        .categories {
            max-width: 1400px;
            margin: 0 auto;
            padding: 24px;
        }

        .category {
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 6px;
            margin-bottom: 24px;
            scroll-margin-top: 140px;
            transition: background-color 0.3s ease, border-color 0.3s ease;
        }

        body.light-mode .category {
            background: #ffffff;
            border: 1px solid #d0d7de;
        }

        .category-header {
            padding: 16px 24px;
            cursor: pointer;
            user-select: none;
            position: sticky;
            top: 132px;
            z-index: 500;
            background: #161b22;
            border-bottom: 1px solid #30363d;
            margin: 0;
            transition: background-color 0.3s ease, border-color 0.3s ease;
        }

        body.light-mode .category-header {
            background: #ffffff;
            border-bottom: 1px solid #d0d7de;
        }

        .category-header:hover {
            background: #1c2128;
        }

        body.light-mode .category-header:hover {
            background: #f6f8fa;
        }

        .category-header h2 {
            font-size: 18px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 4px;
        }

        .toggle-icon {
            transition: transform 0.2s;
            font-size: 14px;
        }

        .toggle-icon.collapsed {
            transform: rotate(-90deg);
        }

        .priority {
            font-size: 11px;
            font-weight: 600;
            padding: 2px 8px;
            border-radius: 12px;
            text-transform: uppercase;
        }

        .priority-1 { background: #da3633; color: white; }
        .priority-2 { background: #fb8500; color: white; }
        .priority-3 { background: #d29922; color: white; }
        .priority-4 { background: #57606a; color: white; }
        .priority-5 { background: #6e7681; color: white; }

        .category-stats {
            margin-left: auto;
            font-size: 14px;
            font-weight: 400;
            color: #8b949e;
        }

        body.light-mode .category-stats {
            color: #57606a;
        }

        .category-description {
            font-size: 14px;
            color: #8b949e;
            margin-top: 4px;
        }

        body.light-mode .category-description {
            color: #57606a;
        }

        .category-summary {
            background: #0d1117;
            border-top: 1px solid #30363d;
            transition: background-color 0.3s ease, border-color 0.3s ease;
        }

        body.light-mode .category-summary {
            background: #f6f8fa;
            border-top: 1px solid #d0d7de;
        }

        .summary-toggle {
            width: 100%;
            background: transparent;
            border: none;
            color: #8b949e;
            padding: 12px 24px;
            text-align: left;
            cursor: pointer;
            font-size: 13px;
            display: flex;
            align-items: center;
            gap: 8px;
            transition: color 0.3s ease;
        }

        body.light-mode .summary-toggle {
            color: #57606a;
        }

        .summary-toggle:hover {
            color: #58a6ff;
        }

        body.light-mode .summary-toggle:hover {
            color: #0969da;
        }

        .summary-toggle .toggle-arrow {
            display: inline-block;
            font-size: 10px;
        }

        .summary-content {
            padding: 16px 24px;
            font-size: 13px;
            line-height: 1.6;
            color: #8b949e;
            border-top: 1px solid #30363d;
            transition: color 0.3s ease, border-color 0.3s ease;
        }

        body.light-mode .summary-content {
            color: #57606a;
            border-top: 1px solid #d0d7de;
        }

        .category-summary.collapsed .summary-content {
            display: none;
        }

        .summary-content p {
            margin: 8px 0;
        }

        .summary-content p:first-child {
            margin-top: 0;
        }

        .summary-content ul {
            margin: 8px 0;
            padding-left: 24px;
        }

        .summary-content li {
            margin: 4px 0;
        }

        .summary-content strong {
            color: #c9d1d9;
            font-weight: 600;
            display: block;
            margin-top: 12px;
            margin-bottom: 4px;
        }

        .summary-content strong:first-child {
            margin-top: 0;
        }

        body.light-mode .summary-content strong {
            color: #24292f;
        }

        .category-content {
            padding: 16px 24px;
        }

        .category-content.collapsed {
            display: none;
        }

        .file {
            margin-bottom: 24px;
            border: 1px solid #30363d;
            border-radius: 6px;
            overflow: visible;
            scroll-margin-top: 220px;
            transition: border-color 0.3s ease;
        }

        body.light-mode .file {
            border: 1px solid #d0d7de;
        }

        .file-header {
            background: #1c2128;
            padding: 8px 16px;
            display: flex;
            align-items: center;
            gap: 12px;
            font-size: 14px;
            font-family: "SF Mono", Monaco, Consolas, monospace;
            position: sticky;
            top: 210px;
            z-index: 400;
            border-bottom: 1px solid #30363d;
            border-top-left-radius: 6px;
            border-top-right-radius: 6px;
            cursor: pointer;
            user-select: none;
            transition: background-color 0.3s ease, border-color 0.3s ease;
        }

        body.light-mode .file-header {
            background: #f6f8fa;
            border-bottom: 1px solid #d0d7de;
        }

        .file-header:hover {
            background: #22272e;
        }

        body.light-mode .file-header:hover {
            background: #eaeef2;
        }

        .file-header .toggle-icon {
            transition: transform 0.2s;
            font-size: 12px;
            color: #8b949e;
        }

        .file-header .toggle-icon.collapsed {
            transform: rotate(-90deg);
        }

        .file-status {
            font-weight: 700;
            width: 20px;
            text-align: center;
        }

        .file-added .file-status { color: #3fb950; }
        .file-removed .file-status { color: #f85149; }
        .file-modified .file-status { color: #d29922; }
        .file-renamed .file-status { color: #58a6ff; }

        .file-path {
            flex: 1;
            color: #f0f6fc;
        }

        body.light-mode .file-path {
            color: #24292f;
        }

        .file-stats {
            display: flex;
            gap: 8px;
            font-size: 12px;
        }

        .file-diff {
            background: #0d1117;
            overflow-x: auto;
            max-height: 60vh;
            overflow-y: auto;
            transition: background-color 0.3s ease;
        }

        body.light-mode .file-diff {
            background: #ffffff;
        }

        .file-diff.collapsed {
            display: none;
        }

        /* Collapsible meta section */
        .diff-meta-section {
            border-bottom: 1px solid #30363d;
            transition: border-color 0.3s ease;
        }

        body.light-mode .diff-meta-section {
            border-bottom: 1px solid #d0d7de;
        }

        .diff-meta-toggle {
            width: 100%;
            background: #161b22;
            border: none;
            color: #8b949e;
            padding: 8px 16px;
            text-align: left;
            cursor: pointer;
            font-size: 12px;
            font-family: "SF Mono", Monaco, Consolas, monospace;
            display: flex;
            align-items: center;
            gap: 8px;
            transition: background-color 0.3s ease, color 0.3s ease;
        }

        body.light-mode .diff-meta-toggle {
            background: #f6f8fa;
            color: #57606a;
        }

        .diff-meta-toggle:hover {
            background: #1c2128;
            color: #c9d1d9;
        }

        body.light-mode .diff-meta-toggle:hover {
            background: #eaeef2;
            color: #24292f;
        }

        .diff-meta-toggle .toggle-arrow {
            transition: transform 0.2s;
            display: inline-block;
        }

        .diff-meta-section:not(.collapsed) .toggle-arrow {
            transform: rotate(90deg);
        }

        .diff-meta-content {
            background: #0d1117;
            color: #6e7681;
            font-size: 11px;
            padding: 12px 16px;
            margin: 0;
            font-family: "SF Mono", Monaco, Consolas, monospace;
            white-space: pre;
            overflow-x: auto;
            transition: background-color 0.3s ease, color 0.3s ease;
        }

        body.light-mode .diff-meta-content {
            background: #ffffff;
            color: #57606a;
        }

        .diff-meta-section.collapsed .diff-meta-content {
            display: none;
        }

        /* Table-based diff with line numbers */
        .diff-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
            line-height: 1.5;
            font-family: "SF Mono", Monaco, Consolas, monospace;
            background: #0d1117;
            transition: background-color 0.3s ease;
        }

        body.light-mode .diff-table {
            background: #ffffff;
        }

        .diff-table tr {
            border: none;
        }

        .line-num {
            padding: 2px 10px;
            text-align: right;
            vertical-align: top;
            user-select: none;
            color: #6e7681;
            background: #0d1117;
            width: 1%;
            min-width: 40px;
            font-size: 11px;
            border-right: 1px solid #21262d;
            transition: background-color 0.3s ease, border-color 0.3s ease, color 0.3s ease;
        }

        body.light-mode .line-num {
            color: #57606a;
            background: #ffffff;
            border-right: 1px solid #d0d7de;
        }

        .line-num a {
            color: #6e7681;
            text-decoration: none;
            display: block;
            padding: 2px 4px;
            margin: -2px -4px;
        }

        body.light-mode .line-num a {
            color: #57606a;
        }

        .line-num a:hover {
            color: #58a6ff;
            text-decoration: underline;
        }

        body.light-mode .line-num a:hover {
            color: #0969da;
        }

        .line-content {
            padding: 2px 10px;
            vertical-align: top;
            white-space: pre;
            overflow-wrap: break-word;
            color: #c9d1d9;
            transition: color 0.3s ease;
        }

        body.light-mode .line-content {
            color: #24292f;
        }

        .line-content span {
            white-space: pre-wrap;
        }

        /* Added lines - GitHub exact colors */
        .diff-line-add .line-num.new-num {
            background: #033a16;
            color: #7ee787;
            transition: background-color 0.3s ease, color 0.3s ease;
        }

        body.light-mode .diff-line-add .line-num.new-num {
            background: #ccffd8;
            color: #1a7f37;
        }

        .diff-line-add .line-content {
            background: #033a16;
            transition: background-color 0.3s ease;
        }

        body.light-mode .diff-line-add .line-content {
            background: #d1f4db;
        }

        .diff-line-add .line-content .diff-add {
            color: #c9d1d9;
            transition: color 0.3s ease;
        }

        body.light-mode .diff-line-add .line-content .diff-add {
            color: #1f2328;
        }

        /* Deleted lines - GitHub exact colors */
        .diff-line-del .line-num.old-num {
            background: #5a1e1e;
            color: #ff7b72;
            transition: background-color 0.3s ease, color 0.3s ease;
        }

        body.light-mode .diff-line-del .line-num.old-num {
            background: #ffd7d5;
            color: #a40e26;
        }

        .diff-line-del .line-content {
            background: #5a1e1e;
            transition: background-color 0.3s ease;
        }

        body.light-mode .diff-line-del .line-content {
            background: #ffd8d3;
        }

        .diff-line-del .line-content .diff-del {
            color: #c9d1d9;
            transition: color 0.3s ease;
        }

        body.light-mode .diff-line-del .line-content .diff-del {
            color: #1f2328;
        }

        /* Context lines */
        .diff-ctx {
            color: #c9d1d9;
            transition: color 0.3s ease;
        }

        body.light-mode .diff-ctx {
            color: #24292f;
        }

        /* Hunk headers */
        .diff-hunk {
            color: #7d8590;
            background-color: rgba(56, 139, 253, 0.15);
            font-weight: 600;
            padding: 4px 8px;
            display: inline-block;
            transition: background-color 0.3s ease, color 0.3s ease;
        }

        body.light-mode .diff-hunk {
            color: #57606a;
            background-color: rgba(9, 105, 218, 0.1);
        }

        /* Inline change highlighting - GitHub exact colors */
        .diff-line-add .diff-add mark {
            background-color: #1f6feb;
            color: #c9d1d9;
            padding: 0;
            border-radius: 2px;
            transition: background-color 0.3s ease, color 0.3s ease;
        }

        body.light-mode .diff-line-add .diff-add mark {
            background-color: #54aeff;
            color: #1f2328;
        }

        .diff-line-del .diff-del mark {
            background-color: #8e1519;
            color: #c9d1d9;
            padding: 0;
            border-radius: 2px;
            transition: background-color 0.3s ease, color 0.3s ease;
        }

        body.light-mode .diff-line-del .diff-del mark {
            background-color: #ff9492;
            color: #1f2328;
        }
        """

    def _get_javascript(self) -> str:
        """Return embedded JavaScript"""
        # Read main JS file
        main_js_path = Path(__file__).parent / "static" / "pr-diff-viewer.js"
        if main_js_path.exists():
            return main_js_path.read_text(encoding="utf-8")

        # Fallback to inline JS if file not found
        return """
        function toggleCategory(id) {
            const content = document.getElementById('content-' + id);
            const toggle = document.getElementById('toggle-' + id);

            if (content.classList.contains('collapsed')) {
                content.classList.remove('collapsed');
                toggle.classList.remove('collapsed');
            } else {
                content.classList.add('collapsed');
                toggle.classList.add('collapsed');
            }
        }

        function toggleSummary(id) {
            const summary = document.getElementById('summary-' + id);
            const arrow = document.getElementById('summary-arrow-' + id);

            if (summary.classList.contains('collapsed')) {
                summary.classList.remove('collapsed');
                arrow.textContent = '▼';
            } else {
                summary.classList.add('collapsed');
                arrow.textContent = '▶';
            }
        }

        function toggleFile(fileId) {
            const diff = document.getElementById('diff-' + fileId);
            const toggle = document.getElementById('toggle-' + fileId);
            const fileElement = diff.closest('.file');

            if (diff.classList.contains('collapsed')) {
                // Expanding - just expand it
                diff.classList.remove('collapsed');
                toggle.classList.remove('collapsed');
            } else {
                // Collapsing - collapse it then scroll smartly
                diff.classList.add('collapsed');
                toggle.classList.add('collapsed');

                // Find the category this file belongs to
                const category = fileElement.closest('.category');
                if (!category) return;

                // Get all files in this category
                const allFilesInCategory = Array.from(category.querySelectorAll('.file'));
                const currentFileIndex = allFilesInCategory.indexOf(fileElement);

                // Find the next uncollapsed file after this one
                let targetElement = null;
                for (let i = currentFileIndex + 1; i < allFilesInCategory.length; i++) {
                    const fileDiff = allFilesInCategory[i].querySelector('.file-diff');
                    if (fileDiff && !fileDiff.classList.contains('collapsed')) {
                        targetElement = allFilesInCategory[i];
                        break;
                    }
                }

                // If no uncollapsed file found after this one, check before it
                if (!targetElement) {
                    for (let i = 0; i < currentFileIndex; i++) {
                        const fileDiff = allFilesInCategory[i].querySelector('.file-diff');
                        if (fileDiff && !fileDiff.classList.contains('collapsed')) {
                            targetElement = allFilesInCategory[i];
                            break;
                        }
                    }
                }

                // If still no uncollapsed file found, all are collapsed - scroll to category header
                if (!targetElement) {
                    targetElement = category.querySelector('.category-header');
                }

                // Scroll to the target element smoothly
                if (targetElement) {
                    targetElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
            }
        }

        function toggleMeta(fileId) {
            const meta = document.getElementById('meta-' + fileId);
            if (meta.classList.contains('collapsed')) {
                meta.classList.remove('collapsed');
            } else {
                meta.classList.add('collapsed');
            }
        }

        function toggleTheme() {
            const checkbox = document.getElementById('theme-toggle-checkbox');
            const body = document.body;

            if (checkbox.checked) {
                body.classList.add('light-mode');
                localStorage.setItem('theme', 'light');
            } else {
                body.classList.remove('light-mode');
                localStorage.setItem('theme', 'dark');
            }
        }

        function toggleFormatting() {
            const checkbox = document.getElementById('formatting-toggle-checkbox');
            const body = document.body;

            if (checkbox.checked) {
                body.classList.add('hide-formatting');
                localStorage.setItem('hideFormatting', 'true');
            } else {
                body.classList.remove('hide-formatting');
                localStorage.setItem('hideFormatting', 'false');
            }
        }

        // Initialize theme from localStorage
        (function() {
            const savedTheme = localStorage.getItem('theme');
            const checkbox = document.getElementById('theme-toggle-checkbox');

            if (savedTheme === 'light') {
                document.body.classList.add('light-mode');
                checkbox.checked = true;
            }
        })();

        // Initialize formatting toggle from localStorage
        (function() {
            const hideFormatting = localStorage.getItem('hideFormatting');
            const checkbox = document.getElementById('formatting-toggle-checkbox');

            // Default to hiding formatting changes (checked by default in HTML)
            if (hideFormatting === null || hideFormatting === 'true') {
                document.body.classList.add('hide-formatting');
                checkbox.checked = true;

                // Auto-collapse formatting-only files on initial load
                document.querySelectorAll('.file.formatting-only').forEach(file => {
                    const fileId = file.querySelector('.file-diff').id.replace('diff-', '');
                    const diff = document.getElementById('diff-' + fileId);
                    const toggle = document.getElementById('toggle-' + fileId);

                    if (diff && toggle && !diff.classList.contains('collapsed')) {
                        diff.classList.add('collapsed');
                        toggle.classList.add('collapsed');
                    }
                });
            } else {
                document.body.classList.remove('hide-formatting');
                checkbox.checked = false;
            }
        })();

        // Track visible categories and files
        document.addEventListener('DOMContentLoaded', function() {
            const categories = document.querySelectorAll('.category');
            const files = document.querySelectorAll('.file');

            // Add click-to-collapse on category headers when sticky
            const categoryHeaders = document.querySelectorAll('.category-header');
            categoryHeaders.forEach((header, index) => {
                // Make the entire header clickable but preserve the toggle functionality
                header.style.cursor = 'pointer';
            });

            // Intersection Observer for tracking visible elements
            const observerOptions = {
                root: null,
                rootMargin: '-80px 0px -80% 0px',
                threshold: 0
            };

            let currentCategory = null;
            let currentFile = null;

            const categoryObserver = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        const categoryName = entry.target.dataset.categoryName;
                        if (categoryName) {
                            currentCategory = categoryName;
                            updateBreadcrumb();
                        }
                    }
                });
            }, observerOptions);

            const fileObserver = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        const filePath = entry.target.dataset.filePath;
                        if (filePath) {
                            currentFile = filePath;
                            updateBreadcrumb();
                        }
                    }
                });
            }, observerOptions);

            function updateBreadcrumb() {
                // This function can be used to update a breadcrumb if we add one
                // For now, it just tracks the current position
                console.log('Current:', currentCategory, '>', currentFile);
            }

            categories.forEach(cat => categoryObserver.observe(cat));
            files.forEach(file => fileObserver.observe(file));

            // Apply Prism syntax highlighting to diff content
            if (typeof Prism !== 'undefined') {
                document.querySelectorAll('.diff-table').forEach(table => {
                    // Get language from parent file element
                    const fileDiv = table.closest('.file');
                    const language = fileDiv ? fileDiv.dataset.language : '';

                    if (language && Prism.languages[language]) {
                        // Apply syntax highlighting to each line's content
                        table.querySelectorAll('.line-content').forEach(cell => {
                            const spans = cell.querySelectorAll('.diff-add, .diff-del, .diff-ctx');
                            spans.forEach(span => {
                                const text = span.textContent;
                                if (text && text.trim()) {
                                    try {
                                        const highlighted = Prism.highlight(text, Prism.languages[language], language);
                                        // Preserve the original class and wrap in a span with highlighted content
                                        const tempDiv = document.createElement('div');
                                        tempDiv.innerHTML = highlighted;
                                        span.innerHTML = tempDiv.innerHTML;
                                    } catch (e) {
                                        // If highlighting fails, keep original text
                                        console.warn('Prism highlighting failed:', e);
                                    }
                                }
                            });
                        });
                    }
                });
            }
        });
        """


