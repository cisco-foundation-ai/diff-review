#!/usr/bin/env python3
"""CLI entry point for pr-diff-review."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from pr_diff_review.categorizer import LLMCategorizer, OpenAICategorizer, PatternCategorizer
from pr_diff_review.fetcher import PRDiffFetcher
from pr_diff_review.html_generator import HTMLGenerator
from pr_diff_review.server import PRDiffServer, find_available_port


def install_skill() -> None:
    """Install the Claude Code skill to the current repository."""
    cwd = Path.cwd()
    claude_skills_dir = cwd / ".claude" / "skills" / "diff-review"

    if claude_skills_dir.exists():
        print(f"✓ Skill already installed at {claude_skills_dir}")
        return

    claude_skills_dir.mkdir(parents=True, exist_ok=True)

    package_dir = Path(__file__).parent.parent
    skill_source = package_dir.parent / ".claude-skill" / "SKILL.md"
    skill_dest = claude_skills_dir / "SKILL.md"

    if not skill_source.exists():
        print(f"❌ Error: Skill source not found at {skill_source}", file=sys.stderr)
        sys.exit(1)

    import shutil
    shutil.copy(skill_source, skill_dest)

    print(f"✓ Skill installed to {claude_skills_dir}")
    print("\nYou can now use: /diff-review <pr-number>")


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Generate categorized HTML diff viewer for GitHub PRs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s 630
  %(prog)s --pr 630 --repo owner/repo
  %(prog)s 630 --output my-diff.html --no-llm
  %(prog)s install-skill  # Install Claude Code skill

Environment:
  ANTHROPIC_API_KEY - Claude API key for LLM categorization (optional)
  OPENAI_API_KEY - OpenAI API key as fallback (optional)
        """,
    )
    parser.add_argument("pr_number", type=str, nargs="?", help="PR number or 'install-skill'")
    parser.add_argument(
        "--pr", type=int, dest="pr_number_alt", help="PR number (alternative flag)"
    )
    parser.add_argument(
        "--repo", type=str, help="Repository (owner/repo), defaults to current repo"
    )
    parser.add_argument("--output", "-o", type=str, help="Output HTML file path")
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Skip LLM, use pattern-based categorization",
    )
    parser.add_argument(
        "--link-mode",
        type=str,
        choices=["diff", "blob", "file"],
        default="diff",
        help="Link mode: 'diff' for line anchors (works on small PRs, allows comments), 'file' for file anchors (always works), 'blob' for direct line links (can't comment)",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Start local server with live diff generation and comment support (no file saved)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port for local server (default: auto-detect starting from 8080)",
    )

    args = parser.parse_args()

    # Handle install-skill command
    if args.pr_number == "install-skill":
        install_skill()
        return

    # Determine PR number
    pr_number_str = args.pr_number or args.pr_number_alt
    if not pr_number_str:
        parser.error("PR number required (either positional or --pr)")

    try:
        pr_number = int(pr_number_str)
    except (ValueError, TypeError):
        parser.error(f"Invalid PR number: {pr_number_str}")

    # Determine repository
    if args.repo:
        repo = args.repo
    else:
        try:
            result = subprocess.run(
                ["gh", "repo", "view", "--json", "nameWithOwner"],
                capture_output=True,
                text=True,
                check=True,
            )
            repo_data = json.loads(result.stdout)
            repo = repo_data["nameWithOwner"]
        except Exception as e:
            print(
                "Error: Could not detect repository. Use --repo flag.", file=sys.stderr
            )
            print(f"Details: {e}", file=sys.stderr)
            sys.exit(1)

    # Determine output path
    if args.output:
        output_path = Path(args.output).resolve()
        dangerous_prefixes = ["/etc", "/sys", "/proc", "/dev", "/boot"]
        if any(str(output_path).startswith(prefix) for prefix in dangerous_prefixes):
            print(
                f"  ⚠️  WARNING: Writing to system directory: {output_path}",
                file=sys.stderr,
            )
    else:
        output_path = Path(f"pr-{pr_number}-categorized-diff.html").resolve()

    print(f"Fetching PR #{pr_number} from {repo}...")

    fetcher = PRDiffFetcher(repo, pr_number)
    try:
        pr_info, files, diff_hashes = fetcher.fetch_all()
    except subprocess.CalledProcessError:
        print(
            "Error: Failed to fetch PR data. Is gh CLI authenticated?", file=sys.stderr
        )
        print("Run: gh auth login", file=sys.stderr)
        sys.exit(1)

    print(f"✓ Fetched {len(files)} files")

    # Categorize files
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    if not args.no_llm and (anthropic_key or openai_key):
        try:
            if anthropic_key:
                print("Categorizing with Claude API...")
                categorizer = LLMCategorizer(anthropic_key)
                categories = categorizer.categorize(pr_info, files)
                print(f"✓ Created {len(categories)} categories (Claude)")
            else:
                print("Categorizing with OpenAI API...")
                categorizer_openai = OpenAICategorizer(openai_key)  # type: ignore[arg-type]
                categories = categorizer_openai.categorize(pr_info, files)
                print(f"✓ Created {len(categories)} categories (OpenAI)")
        except Exception as e:
            print(f"Warning: LLM categorization failed: {e}", file=sys.stderr)
            print("Falling back to pattern-based categorization...", file=sys.stderr)
            categorizer = PatternCategorizer()
            categories = categorizer.categorize(files)
            print(f"✓ Created {len(categories)} categories (patterns)")
    else:
        if args.no_llm:
            print("Using pattern-based categorization (--no-llm)...")
        else:
            print(
                "No API key found (ANTHROPIC_API_KEY or OPENAI_API_KEY), using pattern-based categorization..."
            )
        categorizer = PatternCategorizer()
        categories = categorizer.categorize(files)
        print(f"✓ Created {len(categories)} categories")

    # Generate PR review (if using LLM)
    pr_review = None
    if not args.no_llm and hasattr(categorizer, "generate_review"):
        try:
            print("Generating PR review summary...")
            pr_review = categorizer.generate_review(pr_info, categories)  # type: ignore[attr-defined]
            print("✓ PR review generated")
        except Exception as e:
            print(f"Warning: PR review generation failed: {e}", file=sys.stderr)
            pr_review = None

    # Dual-mode behavior
    if args.serve:
        if args.port is None:
            port = find_available_port(start_port=8080)
        else:
            port = args.port

        server = PRDiffServer(
            pr_info=pr_info,
            files=files,
            diff_hashes=diff_hashes,
            categories=categories,
            repo=repo,
            pr_number=pr_number,
            commit_sha=fetcher.head_sha,
            port=port,
            link_mode=args.link_mode,
            pr_review=pr_review,
            file_fetcher=fetcher,
        )

        try:
            server.start()
        except KeyboardInterrupt:
            print("\n\n✓ Server stopped")
    else:
        print(f"Generating HTML with {args.link_mode} links...")
        generator = HTMLGenerator(
            link_mode=args.link_mode,
            head_sha=fetcher.head_sha,
            repo=repo,
            embed_assets=True,
            file_fetcher=fetcher,
        )
        generator.generate(pr_info, categories, output_path, diff_hashes, pr_review)

        print("\n✓ Done! Open in browser:")
        print(f"  open {output_path}")


if __name__ == "__main__":
    main()
