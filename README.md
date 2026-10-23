# PyTestForge

**PyTestForge** is an AST-driven static code analyzer and automated pytest unit suite synthesizer. Instead of feeding entire codebases blindly into an LLM, PyTestForge parses local Python Abstract Syntax Trees (ast), computes McCabe cyclomatic complexity per function, identifies untested high-complexity nodes, and synthesizes deterministic pytest suites using OpenAI models.

## Key Capabilities

- **Zero-Token Local AST Auditing (`--audit-only`):** Inspect function complexity, missing docstrings, and missing return type annotations locally without making API calls.
- **Complexity-Gated Test Synthesis (`--min-complexity`):** Reduce token consumption by targeting only complex functions that require thorough boundary and exception testing.
- **Selective AST Node Extraction:** Extracts isolated function signatures and bodies rather than transmitting whole files.

## Installation

```bash
git clone [https://github.com/rihat3645-hub/PyTestForge.git](https://github.com/rihat3645-hub/PyTestForge.git)
cd PyTestForge
pip install -e ".[dev]"
```

## Usage

### 1. Local Static AST Audit (No API Key Required)

```bash
pytestforge path/to/module.py --audit-only
```

### 2. Automated Pytest Suite Generation

```bash
export OPENAI_API_KEY="sk-..."
pytestforge path/to/module.py --min-complexity 3 -o tests/test_module.py
```

## Running Tests

```bash
pytest -v
```

## License

MIT License
