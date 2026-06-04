"""AI-use disclosure report builder for Research Ledger.

Reads the local ledger state and produces a structured disclosure draft
in either JSON or Markdown format.  The report is intended as a starting
point for researchers to review, edit, and submit according to their
institutional requirements.
"""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from research_ledger.ledger import Ledger, Seal


def build_disclosure_report(ledger: Ledger) -> dict[str, Any]:
    """Build a disclosure report dict from the current ledger state.

    The returned dict contains ledger identity, verification status,
    event type counts, per-event summaries (including metadata), seal
    summaries, and a list of known limitations in Traditional Chinese.

    Args:
        ledger: An initialized :class:`~research_ledger.ledger.Ledger`.

    Returns:
        A JSON-serializable dict suitable for :func:`render_json` or
        :func:`render_markdown`.
    """
    metadata = ledger.metadata()
    genesis = ledger.genesis()
    scope = ledger.scope()
    events = ledger.events()
    verification = ledger.verify()
    seals = _read_seals(ledger)
    event_type_counts = dict(sorted(Counter(event.event_type for event in events).items()))

    return {
        "report_type": "ai_use_disclosure_draft",
        "ledger_id": metadata.ledger_id,
        "schema_version": metadata.schema_version,
        "canonicalization_version": metadata.canonicalization_version,
        "genesis_event_hash": genesis.event_hash,
        "trusted_key_id": metadata.key_id,
        "scope": {
            "title": scope.title,
            "description": scope.description,
            "included_paths": scope.included_paths,
            "excluded_paths": scope.excluded_paths,
            "recording_policy": scope.recording_policy,
            "scope_hash": scope.event_hash,
        },
        "verification": {
            "ok": verification.ok,
            "event_count": verification.event_count,
            "issues": verification.issues,
            "warnings": verification.warnings,
        },
        "event_count": len(events),
        "event_type_counts": event_type_counts,
        "events": [
            {
                "sequence": event.sequence,
                "event_id": event.event_id,
                "event_type": event.event_type,
                "created_at": event.created_at,
                "content_path": event.content_path,
                "content_hash": event.content_hash,
                "snapshot_path": event.snapshot_path,
                "event_hash": event.event_hash,
                "metadata": event.metadata,
            }
            for event in events
        ],
        "seals": [
            {
                "label": seal.label,
                "created_at": seal.created_at,
                "event_count": seal.event_count,
                "merkle_root": seal.merkle_root,
                "tip_event_hash": seal.tip_event_hash,
            }
            for seal in seals
        ],
        "limitations": [
            "本揭露草稿僅依已記錄事件產生，僅供作者人工審閱與改寫。",
            "本揭露草稿不代表研究品質認證、來源可靠性認證、AI 使用完整揭露、法律證據能力或任何學校／期刊規範之合規結論。",
            "Research Ledger 不證明命題為真。",
            "Research Ledger 不保證來源可靠。",
            "Research Ledger 不保證作者完整記錄所有研究步驟。",
            "研究範圍宣告只定義 eligible research-note boundary，不代表範圍內所有檔案都已被記錄。",
            "本地 ledger 無法單獨阻止持有私鑰者重寫整條歷史。",
        ],
    }


def render_json(report: dict[str, Any]) -> str:
    """Render a disclosure report as pretty-printed JSON.

    Args:
        report: Report dict from :func:`build_disclosure_report`.

    Returns:
        JSON string with 2-space indentation, sorted keys, and a
        trailing newline.
    """
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def render_markdown(report: dict[str, Any]) -> str:
    """Render a disclosure report as a Markdown document.

    Sections: Ledger 摘要, 事件類型統計, 事件摘要 (with optional
    metadata JSON blocks), Seal 摘要, and 限制.

    Args:
        report: Report dict from :func:`build_disclosure_report`.

    Returns:
        Markdown string.
    """
    lines = [
        "# AI 使用揭露草稿",
        "",
        "## Ledger 摘要",
        "",
        f"- Ledger ID: `{report['ledger_id']}`",
        f"- Schema version: `{report['schema_version']}`",
        f"- Canonicalization: `{report['canonicalization_version']}`",
        f"- Genesis event hash: `{report['genesis_event_hash']}`",
        f"- Trusted key id: `{report['trusted_key_id']}`",
        f"- Scope hash: `{report['scope']['scope_hash']}`",
        f"- Verification status: {'ok' if report['verification']['ok'] else 'failed'}",
        f"- Verification warnings: {len(report['verification']['warnings'])}",
        f"- Event count: {report['event_count']}",
        "",
        "## 研究範圍宣告",
        "",
        f"- Scope title: {report['scope']['title']}",
        f"- Description: {report['scope']['description']}",
        f"- Recording policy: {report['scope']['recording_policy']}",
        "- Included paths:",
    ]
    for path in report["scope"]["included_paths"]:
        lines.append(f"  - `{path}`")
    lines.append("- Excluded paths:")
    if report["scope"]["excluded_paths"]:
        for path in report["scope"]["excluded_paths"]:
            lines.append(f"  - `{path}`")
    else:
        lines.append("  - None declared.")
    lines.extend(
        [
            "",
            "## 事件類型統計",
            "",
        ]
    )
    if report["event_type_counts"]:
        for event_type, count in report["event_type_counts"].items():
            lines.append(f"- `{event_type}`: {count}")
    else:
        lines.append("- No recorded events.")

    lines.extend(["", "## 事件摘要", ""])
    for event in report["events"]:
        lines.extend(
            [
                f"### {event['sequence']}. {event['event_type']}",
                "",
                f"- Event ID: `{event['event_id']}`",
                f"- Created at: `{event['created_at']}`",
                f"- Content path: `{event['content_path']}`",
                f"- Snapshot path: `{event['snapshot_path']}`",
                f"- Content hash: `{event['content_hash']}`",
                f"- Event hash: `{event['event_hash']}`",
            ]
        )
        if event["metadata"]:
            lines.extend(
                [
                    "- Metadata:",
                    "",
                    "```json",
                    json.dumps(event["metadata"], ensure_ascii=False, indent=2, sort_keys=True),
                    "```",
                ]
            )
        lines.append("")

    lines.extend(["## Seal 摘要", ""])
    if report["seals"]:
        for seal in report["seals"]:
            lines.extend(
                [
                    f"- `{seal['label']}`: {seal['event_count']} events, `{seal['merkle_root']}`",
                ]
            )
    else:
        lines.append("- No seals recorded.")

    lines.extend(["", "## 限制", ""])
    for limitation in report["limitations"]:
        lines.append(f"- {limitation}")
    lines.append("")
    return "\n".join(lines)


def _read_seals(ledger: Ledger) -> list[Seal]:
    """Read and parse all seal files from the ledger's seals directory.

    Args:
        ledger: An initialized :class:`~research_ledger.ledger.Ledger`.

    Returns:
        List of :class:`~research_ledger.ledger.Seal` instances sorted
        by filename (chronological).
    """
    seals = []
    for path in sorted(ledger.seals_dir.glob("*.json")):
        seals.append(Seal(**json.loads(path.read_text(encoding="utf-8"))))
    return seals
