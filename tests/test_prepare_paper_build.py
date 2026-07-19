from __future__ import annotations

from scripts.prepare_paper_build import END, START, prepare


def test_prepare_replaces_wide_summary_table() -> None:
    source = f"before\n{START}\n| Question | Result | Status |\n|---|---|---|\n{END}\nafter\n"
    output = prepare(source)
    assert "| Question |" not in output
    assert "Summary of completed evidence" in output
    assert "4,000 of 4,000" in output
    assert END in output


def test_prepare_requires_section_markers() -> None:
    try:
        prepare("missing markers")
    except ValueError as exc:
        assert "markers" in str(exc)
    else:
        raise AssertionError("prepare should fail when section markers are absent")
