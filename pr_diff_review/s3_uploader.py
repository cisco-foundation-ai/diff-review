import os
import subprocess
import sys
from pathlib import Path
from typing import Any


class S3Uploader:
    """Upload HTML to S3 and return public URL"""

    def __init__(self, bucket: str, region: str = "us-west-2"):
        try:
            import boto3  # type: ignore[import-untyped]

            self.s3 = boto3.client("s3", region_name=region)
            self.bucket = bucket
            self.region = region
        except ImportError:
            raise ImportError("boto3 not installed. Run: pip install boto3")

    def upload(self, html_path: Path, pr_number: int) -> str:
        """Upload HTML file to S3 and return public URL"""
        key = f"pr-diffs/{pr_number}/diff.html"

        with open(html_path, "rb") as f:
            self.s3.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=f,
                ContentType="text/html",
                CacheControl="public, max-age=3600",
                ACL="public-read",
            )

        url = f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{key}"
        return url


def post_pr_comment(repo: str, pr_number: int, url: str) -> None:
    """Post a comment on the PR with the diff viewer URL"""
    comment = f"""🔍 **Categorized Diff Viewer**

View this PR with organized file categories:
👉 [{url}]({url})

Generated with `pr-category-diff.py`
"""

    cmd = ["gh", "pr", "comment", str(pr_number), "--repo", repo, "--body", comment]
    subprocess.run(cmd, check=True)
    print(f"✓ Posted comment on PR #{pr_number}")
