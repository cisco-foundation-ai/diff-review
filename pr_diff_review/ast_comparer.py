import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from tree_sitter import Language, Node, Parser
    from pr_diff_review.fetcher import PRDiffFetcher

try:
    import tree_sitter_javascript
    import tree_sitter_python
    import tree_sitter_typescript
    from tree_sitter import Language, Node, Parser

    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False
    Language = None  # type: ignore[assignment,misc]
    Parser = None  # type: ignore[assignment,misc]
    Node = None  # type: ignore[assignment,misc]


class ASTComparer:
    """Compare code using AST to detect formatting-only changes"""

    def __init__(self, file_fetcher: Optional["PRDiffFetcher"] = None):
        self.parsers: dict[str, Any] = {}
        self.file_fetcher = file_fetcher
        if TREE_SITTER_AVAILABLE:
            self._init_parsers()

    def _init_parsers(self) -> None:
        """Initialize tree-sitter parsers for supported languages"""
        if not TREE_SITTER_AVAILABLE:
            return

        try:
            python_parser = Parser(Language(tree_sitter_python.language()))  # type: ignore[misc]
            self.parsers["python"] = python_parser

            js_parser = Parser(Language(tree_sitter_javascript.language()))  # type: ignore[misc]
            self.parsers["javascript"] = js_parser

            ts_parser = Parser(Language(tree_sitter_typescript.language_typescript()))  # type: ignore[misc]
            self.parsers["typescript"] = ts_parser

            tsx_parser = Parser(Language(tree_sitter_typescript.language_tsx()))  # type: ignore[misc]
            self.parsers["tsx"] = tsx_parser
        except Exception as e:
            print(
                f"Warning: Failed to initialize tree-sitter parsers: {e}",
                file=sys.stderr,
            )
            self.parsers = {}

    def get_language_for_extension(self, file_path: str) -> str | None:
        """Map file extension to parser language"""
        ext = Path(file_path).suffix.lower()
        mapping = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "tsx",
        }
        return mapping.get(ext)

    def are_semantically_equal(
        self,
        old_code: str,
        new_code: str,
        file_path: str,
        old_line_start: int = 0,
        new_line_start: int = 0,
    ) -> bool:
        """
        Compare two code snippets using AST parsing.
        Returns True if they are semantically identical (only formatting differs).

        Args:
            old_code: Old version of code
            new_code: New version of code
            file_path: Path to the file being compared
            old_line_start: Starting line number in old file (1-indexed)
            new_line_start: Starting line number in new file (1-indexed)
        """
        if not TREE_SITTER_AVAILABLE:
            return self._simple_semantic_compare(old_code, new_code)

        lang = self.get_language_for_extension(file_path)
        if not lang or lang not in self.parsers or not self.parsers[lang]:
            return self._simple_semantic_compare(old_code, new_code)

        parser = self.parsers[lang]
        assert parser is not None
        try:
            old_tree = parser.parse(bytes(old_code, "utf8"))
            new_tree = parser.parse(bytes(new_code, "utf8"))

            if old_tree.root_node.has_error or new_tree.root_node.has_error:
                if (
                    self.file_fetcher
                    and self.file_fetcher.base_sha
                    and self.file_fetcher.head_sha
                ):
                    expanded_result = self._compare_with_context_expansion(
                        old_code, new_code, file_path, old_line_start, new_line_start
                    )
                    if expanded_result is not None:
                        return expanded_result
                return self._simple_semantic_compare(old_code, new_code)

            return self._nodes_equal(
                old_tree.root_node, new_tree.root_node, old_code, new_code
            )
        except Exception:
            return self._simple_semantic_compare(old_code, new_code)

    def _compare_with_context_expansion(
        self,
        old_code: str,
        new_code: str,
        file_path: str,
        old_line_start: int,
        new_line_start: int,
    ) -> bool | None:
        """
        Try to expand context around changed lines to get valid AST.
        Returns True/False if successful, None if unable to expand.
        """
        if (
            not self.file_fetcher
            or not self.file_fetcher.base_sha
            or not self.file_fetcher.head_sha
        ):
            return None

        old_file = self.file_fetcher.fetch_file_at_commit(
            file_path, self.file_fetcher.base_sha
        )
        new_file = self.file_fetcher.fetch_file_at_commit(
            file_path, self.file_fetcher.head_sha
        )

        if not old_file or not new_file:
            return None

        old_lines = old_file.split("\n")
        new_lines = new_file.split("\n")

        old_fragment_lines = old_code.count("\n") + 1
        new_fragment_lines = new_code.count("\n") + 1

        lang = self.get_language_for_extension(file_path)
        if not lang or lang not in self.parsers or not self.parsers[lang]:
            return None

        parser = self.parsers[lang]
        assert parser is not None

        max_expansion = 30
        for expansion in range(max_expansion):
            old_start = max(0, old_line_start - 1 - expansion)
            old_end = min(
                len(old_lines), old_line_start - 1 + old_fragment_lines + expansion
            )
            new_start = max(0, new_line_start - 1 - expansion)
            new_end = min(
                len(new_lines), new_line_start - 1 + new_fragment_lines + expansion
            )

            old_expanded = "\n".join(old_lines[old_start:old_end])
            new_expanded = "\n".join(new_lines[new_start:new_end])

            try:
                old_tree = parser.parse(bytes(old_expanded, "utf8"))
                new_tree = parser.parse(bytes(new_expanded, "utf8"))

                if (
                    not old_tree.root_node.has_error
                    and not new_tree.root_node.has_error
                ):
                    return self._nodes_equal(
                        old_tree.root_node,
                        new_tree.root_node,
                        old_expanded,
                        new_expanded,
                    )
            except Exception:
                continue

        return None

    def _simple_semantic_compare(self, old_code: str, new_code: str) -> bool:
        """
        Fallback comparison for code fragments that don't parse.
        Normalizes whitespace, quotes, trailing commas, and grouping parentheses.
        """
        import re

        def normalize(text: str) -> str:
            normalized = "".join(text.split())
            normalized = normalized.replace('"', "'")
            normalized = re.sub(r",(\)|\]|\})", r"\1", normalized)
            if normalized.endswith(","):
                normalized = normalized[:-1]
            normalized = normalized.replace("(", "").replace(")", "")
            return normalized

        old_norm = normalize(old_code)
        new_norm = normalize(new_code)
        return old_norm == new_norm

    def _nodes_equal(self, node1: Node, node2: Node, code1: str, code2: str) -> bool:
        """Recursively compare two AST nodes, ignoring formatting nodes"""
        if self._is_formatting_node(node1) and self._is_formatting_node(node2):
            return True

        if node1.type == "parenthesized_expression" and len(node1.children) > 0:
            for child in node1.children:
                if child.type not in ["(", ")"]:
                    return self._nodes_equal(child, node2, code1, code2)
        if node2.type == "parenthesized_expression" and len(node2.children) > 0:
            for child in node2.children:
                if child.type not in ["(", ")"]:
                    return self._nodes_equal(node1, child, code1, code2)

        if node1.type != node2.type:
            return False

        if node1.is_named and node2.is_named:
            if len(node1.children) == 0 and len(node2.children) == 0:
                text1 = code1[node1.start_byte : node1.end_byte]
                text2 = code2[node2.start_byte : node2.end_byte]
                return self._normalize_literal(text1) == self._normalize_literal(text2)

        children1 = [
            c
            for c in node1.children
            if not self._is_formatting_node(c)
            and not self._is_trailing_comma(c, node1.children)
        ]
        children2 = [
            c
            for c in node2.children
            if not self._is_formatting_node(c)
            and not self._is_trailing_comma(c, node2.children)
        ]

        if len(children1) != len(children2):
            return False

        return all(
            self._nodes_equal(c1, c2, code1, code2)
            for c1, c2 in zip(children1, children2, strict=False)
        )

    def _is_trailing_comma(self, node: Node, siblings: list) -> bool:
        """Check if a node is a trailing comma"""
        if node.type != ",":
            return False

        try:
            idx = siblings.index(node)
        except ValueError:
            return False

        for i in range(idx + 1, len(siblings)):
            sibling = siblings[i]
            if not self._is_formatting_node(sibling) and sibling.type not in [
                ")",
                "]",
                "}",
            ]:
                return False

        return True

    def _is_formatting_node(self, node: Node) -> bool:
        """Check if a node represents formatting (whitespace, comments)"""
        formatting_types = {"comment", "line_comment", "block_comment"}
        return node.type in formatting_types

    def _normalize_literal(self, text: str) -> str:
        """Normalize literals to ignore formatting differences"""
        text = text.strip()
        if (text.startswith('"') and text.endswith('"')) or (
            text.startswith("'") and text.endswith("'")
        ):
            return text[1:-1]
        return text
