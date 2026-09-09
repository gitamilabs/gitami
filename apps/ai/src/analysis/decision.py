from dataclasses import dataclass, field
from typing import List, Literal
from src.analysis.blast_radius import BlastRadiusResult
from src.analysis.conventions import ConventionViolation

Verdict = Literal["ACCEPT", "SUGGEST"]


@dataclass
class Suggestion:
    file_path: str
    line: int
    description: str
    category: Literal["blast_radius", "convention"]
    severity: str = "warning"


@dataclass
class DecisionResult:
    verdict: Verdict
    risk_score: float
    suggestions: List[Suggestion] = field(default_factory=list)
    summary: str = ""


def make_decision(
    blast_radius: BlastRadiusResult,
    violations: List[ConventionViolation],
    risk_threshold: float = 5.0,
) -> DecisionResult:
    """Evaluate blast radius and convention checks to produce ACCEPT or SUGGEST verdict."""
    suggestions: List[Suggestion] = []

    # 1. Add suggestions from convention violations
    for v in violations:
        suggestions.append(
            Suggestion(
                file_path=v.file_path,
                line=v.line,
                description=f"[{v.rule_id}] {v.message}",
                category="convention",
                severity=v.severity,
            )
        )

    # 2. Add suggestions from high blast-radius downstream impact
    if blast_radius.risk_score > risk_threshold:
        affected_summary = ", ".join(a.qualified_name for a in blast_radius.affected_symbols[:3])
        suggestions.append(
            Suggestion(
                file_path=blast_radius.changed_symbols[0] if blast_radius.changed_symbols else "PR",
                line=1,
                description=f"[BLAST_RADIUS] Change has high ripple impact (risk_score={blast_radius.risk_score}). "
                f"Affects {blast_radius.total_affected} downstream symbols: {affected_summary}...",
                category="blast_radius",
                severity="warning",
            )
        )

    has_violations = len(suggestions) > 0
    has_high_blast_radius = blast_radius.risk_score > risk_threshold

    if has_violations or has_high_blast_radius:
        verdict: Verdict = "SUGGEST"
        summary = f"PR evaluation requires maintainer review. {len(suggestions)} suggestion(s) generated."
    else:
        verdict = "ACCEPT"
        summary = "PR passed blast radius and convention checks cleanly."

    return DecisionResult(
        verdict=verdict,
        risk_score=blast_radius.risk_score,
        suggestions=suggestions,
        summary=summary,
    )
