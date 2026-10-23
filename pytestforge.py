#!/usr/bin/env python3
"""
PyTestForge: AST-Driven Static Analyzer & Automated Pytest Generator.
Parses Python source files into Abstract Syntax Trees (AST), calculates
cyclomatic complexity, detects missing docstrings/type-hints, and generates
deterministic pytest unit suites via OpenAI models.
"""

import ast
import os
import sys
import json
import argparse
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional


@dataclass
class FunctionMetrics:
    name: str
    lineno: int
    end_lineno: int
    args: List[str]
    has_return_annotation: bool
    has_docstring: bool
    complexity: int
    is_async: bool
    source_segment: str


class ComplexityVisitor(ast.NodeVisitor):
    """Calculates McCabe-style cyclomatic complexity for a given AST node."""

    def __init__(self) -> None:
        self.complexity = 1

    def visit_If(self, node: ast.If) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        self.complexity += len(node.values) - 1
        self.generic_visit(node)


def analyze_source_code(source: str) -> List[FunctionMetrics]:
    """Parses Python source code and extracts AST metrics for all functions."""
    tree = ast.parse(source)
    lines = source.splitlines()
    metrics_list: List[FunctionMetrics] = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            visitor = ComplexityVisitor()
            visitor.visit(node)

            start = node.lineno - 1
            end = getattr(node, "end_lineno", node.lineno)
            segment = "\n".join(lines[start:end])

            arg_names = [arg.arg for arg in node.args.args]
            has_doc = ast.get_docstring(node) is not None
            has_ret = node.returns is not None

            metrics_list.append(
                FunctionMetrics(
                    name=node.name,
                    lineno=node.lineno,
                    end_lineno=end,
                    args=arg_names,
                    has_return_annotation=has_ret,
                    has_docstring=has_doc,
                    complexity=visitor.complexity,
                    is_async=isinstance(node, ast.AsyncFunctionDef),
                    source_segment=segment,
                )
            )

    return sorted(metrics_list, key=lambda x: x.lineno)


def format_audit_report(filepath: str, metrics: List[FunctionMetrics]) -> str:
    """Formats a clean CLI table summarizing AST audit results."""
    if not metrics:
        return f"No functions discovered in {filepath}."

    header = (
        f"\nAST Audit Report for: {filepath}\n"
        + "=" * 78 + "\n"
        + f"{'Function':<28} {'Lines':<12} {'Complexity':<12} {'Docstring':<12} {'TypeHint':<10}\n"
        + "-" * 78
    )
    rows = [header]
    for m in metrics:
        line_range = f"{m.lineno}-{m.end_lineno}"
        doc_status = "Yes" if m.has_docstring else "MISSING"
        ret_status = "Yes" if m.has_return_annotation else "MISSING"
        rows.append(
            f"{m.name:<28} {line_range:<12} {m.complexity:<12} {doc_status:<12} {ret_status:<10}"
        )
    rows.append("=" * 78)
    return "\n".join(rows)


def synthesize_pytest_suite(
    module_name: str,
    targets: List[FunctionMetrics],
    model: str = "gpt-4o-mini",
) -> str:
    """Generates deterministic pytest test cases for target AST nodes using OpenAI."""
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY environment variable is required for test synthesis.")

    client = OpenAI(api_key=api_key)

    payload = [
        {
            "function": t.name,
            "complexity": t.complexity,
            "is_async": t.is_async,
            "source": t.source_segment,
        }
        for t in targets
    ]

    system_prompt = (
        "You are a senior Python QA architect. Given extracted AST function nodes, "
        "generate a complete, runnable pytest module covering happy paths, boundary conditions, "
        "and exception handling. Return ONLY valid Python code without markdown fences."
    )

    user_prompt = (
        f"Target Module: {module_name}\n"
        f"Extracted AST Nodes:\n{json.dumps(payload, indent=2)}\n\n"
        "Generate comprehensive pytest unit tests."
    )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
    )
    return response.choices[0].message.content.strip()


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pytestforge",
        description="AST-driven static analyzer and automated pytest suite generator.",
    )
    parser.add_argument("target", help="Path to the Python file to inspect.")
    parser.add_argument(
        "--audit-only",
        action="store_true",
        help="Run local AST complexity and docstring audit without calling OpenAI API.",
    )
    parser.add_argument(
        "--min-complexity",
        type=int,
        default=1,
        help="Only generate tests for functions with complexity >= threshold (default: 1).",
    )
    parser.add_argument(
        "-o", "--output",
        help="Output path for the generated pytest file (prints to stdout if omitted).",
    )
    parser.add_argument(
        "-m", "--model",
        default="gpt-4o-mini",
        help="OpenAI model to use for synthesis (default: gpt-4o-mini).",
    )

    args = parser.parse_args(argv)
    target_path = Path(args.target)

    if not target_path.is_file():
        print(f"Error: File '{target_path}' does not exist.", file=sys.stderr)
        return 1

    source = target_path.read_text(encoding="utf-8")
    metrics = analyze_source_code(source)
    print(format_audit_report(str(target_path), metrics))

    if args.audit_only:
        return 0

    filtered = [m for m in metrics if m.complexity >= args.min_complexity]
    if not filtered:
        print(f"No functions matched complexity >= {args.min_complexity}.")
        return 0

    try:
        suite_code = synthesize_pytest_suite(
            module_name=target_path.stem,
            targets=filtered,
            model=args.model,
        )
    except Exception as exc:
        print(f"Synthesis failed: {exc}", file=sys.stderr)
        return 1

    if args.output:
        out_path = Path(args.output)
        out_path.write_text(suite_code + "\n", encoding="utf-8")
        print(f"\nGenerated pytest suite saved to: {out_path}")
    else:
        print("\n--- Generated Pytest Suite ---\n")
        print(suite_code)

    return 0


if __name__ == "__main__":
    sys.exit(main())
  
