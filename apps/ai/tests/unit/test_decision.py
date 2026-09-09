from src.analysis.blast_radius import BlastRadiusResult, AffectedSymbol
from src.analysis.conventions import ConventionViolation
from src.analysis.decision import make_decision


def test_decision_accept_clean():
    blast = BlastRadiusResult(changed_symbols=["math.py::add"], affected_symbols=[], risk_score=0.5)
    violations = []
    res = make_decision(blast, violations)

    assert res.verdict == "ACCEPT"
    assert len(res.suggestions) == 0


def test_decision_suggest_high_risk():
    aff = AffectedSymbol(qualified_name="core.py::run", file_path="core.py", depth=1)
    blast = BlastRadiusResult(changed_symbols=["util.py::helper"], affected_symbols=[aff], risk_score=10.0)
    violations = [
        ConventionViolation(
            rule_id="RULE-001",
            symbol_name="helper",
            file_path="util.py",
            line=10,
            message="Function too long",
            severity="warning",
        )
    ]
    res = make_decision(blast, violations, risk_threshold=5.0)

    assert res.verdict == "SUGGEST"
    assert len(res.suggestions) >= 2
