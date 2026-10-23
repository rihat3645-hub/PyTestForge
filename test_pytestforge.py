import textwrap
from pytestforge import analyze_source_code, format_audit_report


SAMPLE_CODE = textwrap.dedent("""
    def add(a: int, b: int) -> int:
        \"\"\"Adds two integers.\"\"\"
        return a + b

    def evaluate_score(x, y):
        if x > 10 and y > 5:
            for i in range(x):
                if i % 2 == 0:
                    return i
        elif x < 0:
            return -1
        return 0
""")


def test_ast_metrics_extraction():
    metrics = analyze_source_code(SAMPLE_CODE)
    assert len(metrics) == 2

    first = metrics[0]
    assert first.name == "add"
    assert first.has_docstring is True
    assert first.has_return_annotation is True
    assert first.complexity == 1

    second = metrics[1]
    assert second.name == "evaluate_score"
    assert second.has_docstring is False
    assert second.has_return_annotation is False
    assert second.complexity >= 5


def test_audit_report_formatting():
    metrics = analyze_source_code(SAMPLE_CODE)
    report = format_audit_report("sample.py", metrics)
    assert "evaluate_score" in report
    assert "MISSING" in report
  
