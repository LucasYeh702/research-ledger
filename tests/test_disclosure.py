import json

from research_ledger.disclosure import build_disclosure_report, render_markdown
from research_ledger.ledger import Ledger


def test_build_disclosure_report_summarizes_events_and_seals(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    claim = workspace / "claim.md"
    ai_output = workspace / "ai-output.md"
    claim.write_text("研究命題\n", encoding="utf-8")
    ai_output.write_text("AI 提供的反方意見\n", encoding="utf-8")

    ledger = Ledger.init(workspace)
    ledger.record(claim, event_type="claim", metadata={"topic": "AI 使用揭露"})
    ledger.record(ai_output, event_type="ai_output", metadata={"tool": "ChatGPT"})
    ledger.seal(label="draft")

    report = build_disclosure_report(ledger)

    assert report["ledger_id"] == ledger.metadata().ledger_id
    assert report["verification"]["ok"] is True
    assert report["event_count"] == 2
    assert report["event_type_counts"] == {"ai_output": 1, "claim": 1}
    assert report["events"][0]["content_path"] == "claim.md"
    assert report["events"][1]["metadata"] == {"tool": "ChatGPT"}
    assert report["seals"][0]["label"] == "draft"


def test_render_markdown_contains_disclosure_limits_and_event_summary(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    note = workspace / "claim.md"
    note.write_text("研究命題\n", encoding="utf-8")

    ledger = Ledger.init(workspace)
    ledger.record(note, event_type="claim")
    report = build_disclosure_report(ledger)

    markdown = render_markdown(report)

    assert "# AI 使用揭露草稿" in markdown
    assert "Verification status: ok" in markdown
    assert "claim.md" in markdown
    assert "Research Ledger 不證明命題為真" in markdown


def test_disclosure_includes_non_certification_disclaimer(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    note = workspace / "claim.md"
    note.write_text("研究命題\n", encoding="utf-8")

    ledger = Ledger.init(workspace)
    ledger.record(note, event_type="claim")
    report = build_disclosure_report(ledger)
    markdown = render_markdown(report)

    assert any("不代表研究品質認證" in limitation for limitation in report["limitations"])
    assert "不代表研究品質認證" in markdown
    assert "AI 使用完整揭露" in markdown


def test_render_markdown_includes_event_metadata(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    note = workspace / "ai-output.md"
    note.write_text("AI 輸出\n", encoding="utf-8")

    ledger = Ledger.init(workspace)
    ledger.record(note, event_type="ai_output", metadata={"tool": "ChatGPT", "decision": "rejected"})
    report = build_disclosure_report(ledger)

    markdown = render_markdown(report)

    assert '"tool": "ChatGPT"' in markdown
    assert '"decision": "rejected"' in markdown


def test_disclosure_report_is_json_serializable(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    note = workspace / "claim.md"
    note.write_text("研究命題\n", encoding="utf-8")

    ledger = Ledger.init(workspace)
    ledger.record(note, event_type="claim")

    encoded = json.dumps(build_disclosure_report(ledger), ensure_ascii=False)

    assert "claim" in encoded
