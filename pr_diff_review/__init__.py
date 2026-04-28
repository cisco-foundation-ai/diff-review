"""pr-diff-review - Generate categorized HTML diff viewers for GitHub PRs."""

from pr_diff_review.ast_comparer import ASTComparer
from pr_diff_review.categorizer import (
    LLMCategorizer,
    OpenAICategorizer,
    PatternCategorizer,
    PatternDetector,
)
from pr_diff_review.fetcher import PRDiffFetcher
from pr_diff_review.html_generator import HTMLGenerator
from pr_diff_review.models import PRFile, Category
from pr_diff_review.s3_uploader import S3Uploader
from pr_diff_review.server import PRDiffServer

__version__ = "0.1.0"

__all__ = [
    "ASTComparer",
    "Category",
    "LLMCategorizer",
    "OpenAICategorizer",
    "PatternCategorizer",
    "PatternDetector",
    "PRDiffFetcher",
    "PRFile",
    "HTMLGenerator",
    "S3Uploader",
    "PRDiffServer",
]
