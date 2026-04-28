import hashlib
import json
import re
import subprocess
import sys
from typing import Any

from pr_diff_review.models import PRFile


class PRDiffFetcher:
    """Fetches PR data from GitHub using gh CLI"""

    def __init__(self, repo: str, pr_number: int):
        self.repo = repo
        self.pr_number = pr_number
        self.head_sha: str | None = None
        self.base_sha: str | None = None

    def fetch_pr_info(self) -> dict[str, Any]:
        """Fetch basic PR information"""
        cmd = [
            "gh",
            "pr",
            "view",
            str(self.pr_number),
            "--repo",
            self.repo,
            "--json",
            "title,body,author,additions,deletions,files,url,number,headRefOid,baseRefOid",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        self.head_sha = data.get("headRefOid")
        self.base_sha = data.get("baseRefOid")
        return data

    def fetch_full_diff(self) -> str:
        """Fetch the complete PR diff"""
        cmd = ["gh", "pr", "diff", str(self.pr_number), "--repo", self.repo]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout

    def fetch_file_at_commit(self, file_path: str, commit_sha: str) -> str | None:
        """Fetch file contents at a specific commit using git"""
        try:
            cmd = ["git", "show", f"{commit_sha}:{file_path}"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if result.returncode == 0:
                return result.stdout
            return None
        except Exception:
            return None

    def split_diff_by_file(self, full_diff: str) -> dict[str, str]:
        """Split unified diff into per-file diffs"""
        file_diffs = {}
        current_file = None
        current_diff_lines = []

        for line in full_diff.split("\n"):
            if line.startswith("diff --git "):
                if current_file and current_diff_lines:
                    file_diffs[current_file] = "\n".join(current_diff_lines) + "\n"

                parts = line.split()
                if len(parts) >= 4:
                    current_file = parts[3][2:]
                    current_diff_lines = [line]
                else:
                    current_file = None
                    current_diff_lines = []
            elif current_file:
                current_diff_lines.append(line)

        if current_file and current_diff_lines:
            file_diffs[current_file] = "\n".join(current_diff_lines) + "\n"

        return file_diffs

    def fetch_diff_hashes(self) -> dict[str, str]:
        """Fetch GitHub's diff hashes by parsing the PR Files page HTML"""
        cmd = [
            "gh",
            "api",
            f"repos/{self.repo}/pulls/{self.pr_number}",
            "-H",
            "Accept: application/vnd.github.v3.html",
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            html_content = result.stdout

            file_hashes = {}

            pattern = r'id="diff-([a-f0-9]+)"[^>]*data-path="([^"]+)"'
            matches = re.findall(pattern, html_content)

            for diff_hash, file_path in matches:
                file_hashes[file_path] = diff_hash

            if not file_hashes:
                print(
                    "  HTML parsing didn't find hashes, trying diff format...",
                    file=sys.stderr,
                )
                diff_cmd = [
                    "gh",
                    "api",
                    f"repos/{self.repo}/pulls/{self.pr_number}",
                    "-H",
                    "Accept: application/vnd.github.v3.diff",
                ]
                diff_result = subprocess.run(
                    diff_cmd, capture_output=True, text=True, check=True
                )

                for line in diff_result.stdout.split("\n"):
                    if line.startswith("diff --git "):
                        parts = line.split()
                        if len(parts) >= 4:
                            a_path = parts[2]
                            file_path = a_path[2:]

                            hash_val = hashlib.sha256(file_path.encode()).hexdigest()
                            file_hashes[file_path] = hash_val

            return file_hashes
        except Exception as e:
            print(f"Warning: Could not fetch diff hashes: {e}", file=sys.stderr)
            return {}

    def fetch_all(self) -> tuple[dict[str, Any], list[PRFile], dict[str, str]]:
        """Fetch PR info, file diffs, and GitHub diff hashes"""
        pr_info = self.fetch_pr_info()

        print("  Fetching full diff...")
        full_diff = self.fetch_full_diff()
        file_diffs = self.split_diff_by_file(full_diff)

        print("  Fetching GitHub diff hashes...")
        diff_hashes = self.fetch_diff_hashes()

        pr_files = []
        for file_data in pr_info["files"]:
            file_path = file_data["path"]
            diff = file_diffs.get(file_path, "")
            pr_files.append(
                PRFile(
                    path=file_path,
                    additions=file_data["additions"],
                    deletions=file_data["deletions"],
                    status=file_data.get("status", "modified"),
                    diff=diff,
                )
            )

        return pr_info, pr_files, diff_hashes
