import re
from dataclasses import dataclass
from typing import List, Literal, Optional
from ai_service.parsing.models import SymbolNode

Severity = Literal["info", "warning", "error"]


@dataclass
class ConventionViolation:
    rule_id: str
    symbol_name: str
    file_path: str
    line: int
    message: str
    severity: Severity


def check_conventions(
    symbols: List[SymbolNode], max_function_length: int = 50, max_parameters: int = 5
) -> List[ConventionViolation]:
    """Evaluate static convention rules on extracted symbols."""
    violations: List[ConventionViolation] = []

    for sym in symbols:
        # Rule 1: Function length check
        length = sym.end_line - sym.start_line + 1
        if sym.kind in ("function", "method") and length > max_function_length:
            violations.append(
                ConventionViolation(
                    rule_id="RULE-001",
                    symbol_name=sym.name,
                    file_path=sym.file_path,
                    line=sym.start_line,
                    message=f"Function '{sym.name}' exceeds recommended length ({length} lines > {max_function_length}).",
                    severity="warning",
                )
            )

        # Rule 2: Missing docstrings on public Python symbols
        if sym.language == "python" and not sym.name.startswith("_"):
            if sym.kind in ("function", "class") and not sym.docstring:
                violations.append(
                    ConventionViolation(
                        rule_id="RULE-002",
                        symbol_name=sym.name,
                        file_path=sym.file_path,
                        line=sym.start_line,
                        message=f"Public {sym.kind} '{sym.name}' is missing a docstring.",
                        severity="warning",
                    )
                )

        # Rule 3: Naming convention check for classes and components
        if sym.kind in ("class", "component"):
            if sym.name and not sym.name[0].isupper():
                violations.append(
                    ConventionViolation(
                        rule_id="RULE-003",
                        symbol_name=sym.name,
                        file_path=sym.file_path,
                        line=sym.start_line,
                        message=f"{sym.kind.capitalize()} '{sym.name}' should use PascalCase.",
                        severity="error",
                    )
                )

        # Rule 4: Parameter count check from signature
        if sym.kind in ("function", "method") and sym.signature:
            sig_params = sym.signature
            if "(" in sig_params and ")" in sig_params:
                param_str = sig_params[sig_params.find("(") + 1 : sig_params.rfind(")")]
                # Filter out self/cls
                params = [p.strip() for p in param_str.split(",") if p.strip() and p.strip() not in ("self", "cls")]
                if len(params) > max_parameters:
                    violations.append(
                        ConventionViolation(
                            rule_id="RULE-004",
                            symbol_name=sym.name,
                            file_path=sym.file_path,
                            line=sym.start_line,
                            message=f"Function '{sym.name}' has {len(params)} parameters (recommended max is {max_parameters}).",
                            severity="warning",
                        )
                    )

        # Rule 5: TypeScript 'any' type annotation check
        if sym.language in ("typescript", "tsx") and sym.signature:
            if re.search(r":\s*any\b", sym.signature):
                violations.append(
                    ConventionViolation(
                        rule_id="RULE-005",
                        symbol_name=sym.name,
                        file_path=sym.file_path,
                        line=sym.start_line,
                        message=f"Symbol '{sym.name}' uses explicit 'any' type annotation.",
                        severity="warning",
                    )
                )

    return violations


def check_diff_conventions(raw_diff_text: str) -> List[ConventionViolation]:
    """Lint added diff lines for debug statements, secrets, and TODO markers."""
    violations: List[ConventionViolation] = []
    if not raw_diff_text:
        return violations

    patterns = [
        ("RULE-006", r"console\.(log|debug|warn|error)\(", "warning", "Debug console statement left in code"),
        ("RULE-007", r"print\(.*DEBUG", "info", "Debug print statement detected in diff"),
        ("RULE-008", r"(?:TODO|FIXME|HACK|XXX):", "info", "TODO/FIXME marker introduced in PR diff"),
        ("RULE-009", r"(?i)(api_key|password|secret|private_key|token)\s*[:=]\s*['\"][A-Za-z0-9_\-\.]{12,}['\"]", "error", "Potential hardcoded credential or secret detected"),
    ]

    current_file = "diff"
    current_line = 1

    for line in raw_diff_text.splitlines():
        if line.startswith("+++ b/"):
            current_file = line[6:].strip()
            continue
        if line.startswith("@@"):
            match = re.search(r"\+(\d+)", line)
            if match:
                current_line = int(match.group(1))
            continue

        if line.startswith("+") and not line.startswith("+++"):
            code_content = line[1:]
            is_test_file = any(
                t in current_file.lower()
                for t in ("/test/", "/tests/", ".test.", ".spec.", "playwright", "/e2e/", "__tests__", "test_", "_test")
            )
            for rule_id, pattern, severity, message in patterns:
                # Skip debug statements and TODO markers in test/mock files
                if is_test_file and rule_id in ("RULE-006", "RULE-007", "RULE-008"):
                    continue
                if re.search(pattern, code_content):
                    violations.append(
                        ConventionViolation(
                            rule_id=rule_id,
                            symbol_name="",
                            file_path=current_file,
                            line=current_line,
                            message=message,
                            severity=severity,
                        )
                    )
            current_line += 1
        elif not line.startswith("-"):
            current_line += 1

    return violations
