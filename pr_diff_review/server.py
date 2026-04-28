import http.server
import json
import os
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any

from pr_diff_review.html_generator import HTMLGenerator

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore[assignment]


def find_available_port(start_port: int = 8080, max_attempts: int = 100) -> int:
    """Find an available port starting from start_port"""
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind(("127.0.0.1", port))
                return port
        except OSError:
            continue
    raise RuntimeError(
        f"Could not find available port in range {start_port}-{start_port + max_attempts}"
    )


class PRDiffServer:
    """HTTP server with GitHub comment API proxy and on-the-fly generation"""

    def __init__(
        self,
        pr_info: dict[str, Any],
        files: list,
        diff_hashes: dict[str, str],
        categories: list | None,
        repo: str,
        pr_number: int,
        commit_sha: str,
        port: int = 8080,
        link_mode: str = "diff",
        pr_review: str | None = None,
        file_fetcher: Any | None = None,
    ):
        self.pr_info = pr_info
        self.files = files
        self.diff_hashes = diff_hashes
        self.categories = categories
        self.repo = repo
        self.pr_number = pr_number
        self.commit_sha = commit_sha
        self.port = port
        self.link_mode = link_mode
        self.pr_review = pr_review
        self.file_fetcher = file_fetcher
        self.github_token = self._get_github_token()
        self._cached_html: str | None = None  # Cache generated HTML
        self._existing_comments: dict[str, list[dict[str, str]]] | None = (
            None  # Cache fetched comments
        )
        # SSL verification: Can be enabled by setting VERIFY_SSL=1 environment variable
        self.verify_ssl = os.getenv("VERIFY_SSL") == "1"
        if not self.verify_ssl:
            print(
                "  ⚠️  WARNING: SSL verification disabled for GitHub API",
                file=sys.stderr,
            )
            print(
                "      Set VERIFY_SSL=1 to enable (may require SSL certificate setup)",
                file=sys.stderr,
            )

    def _get_github_token(self) -> str:
        """Get GitHub token from environment or gh CLI"""
        # 1. Check GITHUB_TOKEN environment variable
        token = os.getenv("GITHUB_TOKEN")
        if token:
            print("  ✓ Using GITHUB_TOKEN from environment", file=sys.stderr)
            return token

        # 2. Try gh CLI
        try:
            result = subprocess.run(
                ["gh", "auth", "token"], capture_output=True, text=True, check=True
            )
            token = result.stdout.strip()
            if token:
                print("  ✓ Using token from gh CLI", file=sys.stderr)
                return token
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

        # 3. Neither available
        raise ValueError(
            "GitHub token not found. Please either:\n"
            "  1. Set GITHUB_TOKEN environment variable: export GITHUB_TOKEN=ghp_xxx\n"
            "  2. Or authenticate with gh CLI: gh auth login"
        )

    def generate_html(self) -> str:
        """Generate diff HTML on-the-fly without saving to disk"""
        # Import HTMLGenerator from the main script
        import sys
        from pathlib import Path

        # Add tools directory to path to import HTMLGenerator
        tools_dir = Path(__file__).parent
        sys.path.insert(0, str(tools_dir))

        # Import after path is set
        # We'll use a special mode where HTMLGenerator links to external assets
        # For now, let's just generate the HTML with embedded assets
        # and modify it to use external links

        # Generate HTML inline for server mode
        return self._build_html_for_server()

    def _build_html_for_server(self) -> str:
        """Build HTML specifically for server mode with external asset links"""
        # Import necessary functions from main script
        import sys
        from pathlib import Path

        tools_dir = Path(__file__).parent
        sys.path.insert(0, str(tools_dir))

        # We need to use HTMLGenerator but with external links
        # For simplicity, we'll inline the generation logic here
        # Or we can modify HTMLGenerator to support embed_assets=False

        # Calculate total stats
        total_additions = (
            sum(f.additions for cat in self.categories for f in cat.files)
            if self.categories
            else 0
        )
        total_deletions = (
            sum(f.deletions for cat in self.categories for f in cat.files)
            if self.categories
            else 0
        )
        total_files = (
            sum(len(cat.files) for cat in self.categories) if self.categories else 0
        )

        # Generate category sections (simplified - will use HTMLGenerator)
        # For now, return a simple template
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PR #{self.pr_number}: {self.pr_info["title"]}</title>
    <link rel="stylesheet" href="/static/pr-diff-viewer.css">
</head>
<body>
    <div class="header">
        <div class="header-top">
            <h1>PR #{self.pr_number}: {self.pr_info["title"]}</h1>
            <div class="header-actions">
                <button class="general-comment-btn" onclick="showGeneralCommentForm()" title="Add PR comment">
                    💬 Comment on PR
                </button>
                <label class="theme-toggle">
                    <input type="checkbox" id="theme-toggle-checkbox" onchange="toggleTheme()">
                    <span>Light mode</span>
                </label>
            </div>
        </div>
        <div class="pr-meta">
            <span class="author">by {self.pr_info["author"]["login"]}</span>
            <a href="{self.pr_info["url"]}" target="_blank" class="pr-link">View on GitHub →</a>
        </div>
        <div class="pr-stats">
            <span class="stat">{total_files} files changed</span>
            <span class="stat additions">+{total_additions} additions</span>
            <span class="stat deletions">-{total_deletions} deletions</span>
        </div>
    </div>

    <div class="categories">
        <p style="color: #8b949e; text-align: center; padding: 40px;">Loading diff content...</p>
    </div>

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
        window.PR_NUMBER = {self.pr_number};
        window.COMMIT_SHA = '{self.commit_sha}';
    </script>

    <!-- External JavaScript -->
    <script src="/static/pr-diff-viewer.js"></script>
</body>
</html>"""

    def _fetch_existing_comments(self) -> dict:
        """Fetch existing PR comments from GitHub API"""
        if self._existing_comments is not None:
            return self._existing_comments

        if not httpx:
            return {}

        headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json",
        }

        # Fetch line-specific review comments
        line_comments: dict[str, list[dict[str, str]]] = {}
        try:
            client = httpx.Client(verify=self.verify_ssl, timeout=30.0)
            url = f"https://api.github.com/repos/{self.repo}/pulls/{self.pr_number}/comments"
            response = client.get(url, headers=headers)

            if response.status_code == 200:
                comments = response.json()
                for comment in comments:
                    path = comment.get("path")
                    line = comment.get("line") or comment.get("original_line")
                    side = comment.get("side", "RIGHT")

                    if path and line:
                        key = f"{path}:{line}:{side}"
                        if key not in line_comments:
                            line_comments[key] = []
                        line_comments[key].append(
                            {
                                "html_url": comment["html_url"],
                                "body": comment["body"],
                                "user": comment["user"]["login"],
                            }
                        )
        except Exception as e:
            print(f"  Warning: Failed to fetch comments: {e}", file=sys.stderr)

        self._existing_comments = line_comments
        return line_comments

    def handle_comment_post(self, comment_data: dict) -> dict:
        """Post comment or review to GitHub API"""
        if not httpx:
            return {"success": False, "error": "httpx not installed"}

        headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json",
        }

        # Determine endpoint based on comment type
        if "path" in comment_data and "line" in comment_data:
            # Line-specific comment
            url = f"https://api.github.com/repos/{self.repo}/pulls/{self.pr_number}/comments"
            payload = {
                "body": comment_data["body"],
                "commit_id": self.commit_sha,
                "path": comment_data["path"],
                "line": comment_data["line"],
                "side": comment_data["side"],
            }
        elif "review_event" in comment_data:
            # PR review (approve, request changes, comment)
            url = f"https://api.github.com/repos/{self.repo}/pulls/{self.pr_number}/reviews"
            payload = {
                "body": comment_data["body"],
                "event": comment_data[
                    "review_event"
                ],  # COMMENT, APPROVE, REQUEST_CHANGES
            }
        else:
            # General PR comment (issue comment)
            url = f"https://api.github.com/repos/{self.repo}/issues/{self.pr_number}/comments"
            payload = {"body": comment_data["body"]}

        try:
            client = httpx.Client(verify=self.verify_ssl, timeout=30.0)
            response = client.post(url, json=payload, headers=headers)

            if response.status_code == 200 or response.status_code == 201:
                result = response.json()
                # Clear caches so next page load shows the new comment
                self._cached_html = None
                self._existing_comments = None
                return {
                    "success": True,
                    "html_url": result.get(
                        "html_url",
                        result.get("_links", {}).get("html", {}).get("href", ""),
                    ),
                }
            else:
                error_detail = response.json().get("message", "Unknown error")
                return {
                    "success": False,
                    "error": f"{response.status_code}: {error_detail}",
                }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def start(self):
        """Start server"""
        # Create handler class with access to instance variables
        server_instance = self

        class CommentHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
            """Custom handler that serves HTML + static assets + API"""

            def log_message(self, format, *args):
                """Override to reduce log noise"""
                if self.path.startswith("/static/"):
                    return  # Don't log static asset requests
                super().log_message(format, *args)

            def do_POST(self):
                if self.path == "/api/comment":
                    # Parse JSON body
                    content_length = int(self.headers["Content-Length"])
                    post_data = self.rfile.read(content_length)
                    comment_data = json.loads(post_data.decode("utf-8"))

                    # Call server's comment handler
                    result = server_instance.handle_comment_post(comment_data)

                    # Return JSON response
                    self.send_response(200 if result.get("success") else 400)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(json.dumps(result).encode("utf-8"))
                else:
                    self.send_error(404)

            def do_GET(self):
                if self.path == "/":
                    # Generate diff HTML on-the-fly
                    try:
                        html_content = server_instance._generate_full_html()
                        self.send_response(200)
                        self.send_header("Content-Type", "text/html")
                        self.send_header("Cache-Control", "no-cache")
                        self.end_headers()
                        self.wfile.write(html_content.encode("utf-8"))
                    except Exception as e:
                        self.send_error(500, f"Error generating HTML: {e}")
                elif self.path.startswith("/static/"):
                    # Serve static files from tools/static/
                    self.serve_static_file()
                else:
                    self.send_error(404)

            def serve_static_file(self):
                """Serve CSS/JS from tools/static/ directory"""
                # Remove '/static/' prefix and strip query parameters
                requested_file = self.path[8:].split("?")[0]

                # Map request to actual file (allowlist approach prevents path traversal)
                static_files = {
                    "pr-diff-viewer.css": "pr-diff-viewer.css",
                    "pr-diff-viewer.js": "pr-diff-viewer.js",
                    "prism-github-theme.css": "prism-github-theme.css",
                }

                # Get safe filename from allowlist (breaks taint chain for static analysis)
                safe_filename = static_files.get(requested_file)
                if not safe_filename:
                    self.send_error(404, "File not found")
                    return

                # Use constant string from dict (not user input) to construct path
                static_dir = Path(__file__).parent / "static"
                file_path_obj = static_dir / safe_filename

                if file_path_obj.exists() and file_path_obj.is_file():
                    content_type = (
                        "text/css"
                        if safe_filename.endswith(".css")
                        else "application/javascript"
                    )
                    self.send_response(200)
                    self.send_header("Content-Type", content_type)
                    self.send_header("Cache-Control", "no-cache")
                    self.end_headers()
                    with open(file_path_obj, "rb") as f:
                        self.wfile.write(f.read())
                else:
                    self.send_error(404)

        # Create and start server
        handler = CommentHTTPRequestHandler
        server_address = ("127.0.0.1", self.port)

        try:
            httpd = http.server.HTTPServer(server_address, handler)

            print(f"\n✓ Review server started for PR #{server_instance.pr_number}")
            print(f"\n   Access at: http://localhost:{self.port}")
            print("\n   Features:")
            print("   - Click 💬 buttons to comment on lines")
            print("   - Existing comments shown inline")
            print("   - Press Ctrl+C to stop server\n")

            httpd.serve_forever()

        except KeyboardInterrupt:
            pass
        except OSError as e:
            # Address already in use: errno 48 (macOS), errno 98 (Linux)
            if e.errno in (48, 98):
                print(f"\n❌ Port {self.port} is already in use.", file=sys.stderr)
                print("   Try a different port with --port flag", file=sys.stderr)
                sys.exit(1)
            raise

    def _generate_full_html(self) -> str:
        """Generate complete HTML with full diff content (cached after first generation)"""
        if self._cached_html is not None:
            return self._cached_html

        print(
            "  Generating HTML (this may take a moment for large PRs)...",
            file=sys.stderr,
        )

        existing_comments = self._fetch_existing_comments()
        if existing_comments:
            print(
                f"  Found {len(existing_comments)} line(s) with comments",
                file=sys.stderr,
            )

        generator = HTMLGenerator(
            link_mode=self.link_mode,
            head_sha=self.commit_sha,
            repo=self.repo,
            embed_assets=False,
            existing_comments=existing_comments,
            file_fetcher=self.file_fetcher,
        )

        html = generator._build_html(
            self.pr_info, self.categories, self.diff_hashes, self.pr_review
        )

        self._cached_html = html
        print("  ✓ HTML generated and cached", file=sys.stderr)

        return html


if __name__ == "__main__":
    print("This module is meant to be imported by pr-category-diff.py")
    sys.exit(1)
