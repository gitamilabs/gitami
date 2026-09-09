from src.indexer.validator import IndexValidator
from src.indexer.contracts import IndexingStats


def test_validator_success():
    validator = IndexValidator()
    stats = IndexingStats(
        files_discovered=10,
        files_parsed=10,
        files_skipped=0,
        parse_errors=0,
        entities_created=25,
        relationships_created=30,
    )
    report = validator.validate("owner/repo", "c0ffee12345678", stats)
    assert report.is_valid
    assert len(report.fatal_errors) == 0


def test_validator_empty_repo_failure():
    validator = IndexValidator()
    stats = IndexingStats()
    report = validator.validate("", "c0ffee12345678", stats)
    assert not report.is_valid
    assert any("Repository ID is empty" in e for e in report.fatal_errors)


def test_validator_excessive_parse_errors():
    validator = IndexValidator()
    stats = IndexingStats(
        files_discovered=10,
        files_parsed=1,
        parse_errors=9,
    )
    report = validator.validate("owner/repo", "c0ffee12345678", stats)
    assert not report.is_valid
    assert any("Excessive parse failures" in e for e in report.fatal_errors)


def test_validator_minor_warnings_still_valid():
    validator = IndexValidator()
    stats = IndexingStats(
        files_discovered=10,
        files_parsed=9,
        parse_errors=1,
        entities_created=15,
    )
    report = validator.validate("owner/repo", "c0ffee12345678", stats)
    assert report.is_valid
    assert len(report.warnings) >= 1
