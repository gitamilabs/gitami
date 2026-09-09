"""Tests for Markdown-Aware and Semantic Text Splitter."""

from src.vector.splitter import split_markdown_text, split_generic_text


def test_split_markdown_short_text():
    short_text = "## Feature Overview\nThis is a short description of the feature."
    chunks = split_markdown_text(short_text, chunk_size=800)
    assert len(chunks) == 1
    assert chunks[0] == short_text


def test_split_markdown_preserves_structure():
    md_content = (
        "# Main Heading\n\n"
        "## Section 1\n" + ("Detailed paragraph explaining section 1 features in depth.\n" * 10) + "\n\n"
        "## Section 2\n" + ("Detailed paragraph explaining section 2 architecture.\n" * 10)
    )
    chunks = split_markdown_text(md_content, chunk_size=300, chunk_overlap=30)
    assert len(chunks) > 1
    # Check that chunks start cleanly with sections or headings where split
    assert any("Section 1" in c for c in chunks)
    assert any("Section 2" in c for c in chunks)


def test_split_generic_text():
    text = "Paragraph one with several sentences. " * 10 + "\n\n" + "Paragraph two with more details. " * 10
    chunks = split_generic_text(text, chunk_size=200, chunk_overlap=20)
    assert len(chunks) > 1
