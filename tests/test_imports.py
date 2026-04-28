"""Test that all modules can be imported."""

def test_import_main_package():
    """Test importing the main package."""
    import pr_diff_review
    assert pr_diff_review.__version__ == "0.1.0"


def test_import_models():
    """Test importing models."""
    from pr_diff_review.models import PRFile, Category
    assert PRFile is not None
    assert Category is not None


def test_import_fetcher():
    """Test importing fetcher."""
    from pr_diff_review.fetcher import PRDiffFetcher
    assert PRDiffFetcher is not None


def test_import_categorizers():
    """Test importing categorizers."""
    from pr_diff_review.categorizer import (
        PatternCategorizer,
        PatternDetector,
        LLMCategorizer,
        OpenAICategorizer,
    )
    assert PatternCategorizer is not None
    assert PatternDetector is not None
    assert LLMCategorizer is not None
    assert OpenAICategorizer is not None


def test_import_html_generator():
    """Test importing HTML generator."""
    from pr_diff_review.html_generator import HTMLGenerator
    assert HTMLGenerator is not None


def test_import_server():
    """Test importing server."""
    from pr_diff_review.server import PRDiffServer, find_available_port
    assert PRDiffServer is not None
    assert find_available_port is not None


def test_import_ast_comparer():
    """Test importing AST comparer."""
    from pr_diff_review.ast_comparer import ASTComparer
    assert ASTComparer is not None


def test_import_s3_uploader():
    """Test importing S3 uploader."""
    from pr_diff_review.s3_uploader import S3Uploader
    assert S3Uploader is not None
