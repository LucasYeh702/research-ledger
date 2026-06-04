from __future__ import annotations

from pathlib import Path
from typing import List, Literal, Optional
import json

from pydantic import ValidationError
import typer

from research_ledger.bundle import export_audit_bundle
from research_ledger.disclosure import build_disclosure_report, render_json, render_markdown
from research_ledger.ledger import ISSUE_MALFORMED, ISSUE_SNAPSHOT_MISSING, Ledger

app = typer.Typer(help="Local-first tamper-evident ledger for AI-assisted research.")
MALFORMED_EXCEPTIONS = (FileNotFoundError, json.JSONDecodeError, ValidationError)


def _exit_malformed(exc: Exception) -> None:
    typer.echo(str(exc), err=True)
    raise typer.Exit(3) from exc


@app.command()
def init(
    scope_title: Optional[str] = typer.Option(
        None,
        "--scope-title",
        help="Human-readable title for the research-note scope.",
    ),
    scope_description: Optional[str] = typer.Option(
        None,
        "--scope-description",
        help="Plain-language statement of what this ledger is intended to cover.",
    ),
    include_paths: Optional[List[Path]] = typer.Option(
        None,
        "--include",
        help="Workspace-relative path included in the declared research scope. Repeatable.",
    ),
    exclude_paths: Optional[List[Path]] = typer.Option(
        None,
        "--exclude",
        help="Workspace-relative path excluded from the declared research scope. Repeatable.",
    ),
) -> None:
    """Initialize a research ledger in the current directory."""
    try:
        ledger = Ledger.init(
            Path.cwd(),
            scope_title=scope_title,
            scope_description=scope_description,
            include_paths=include_paths,
            exclude_paths=exclude_paths,
        )
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2) from exc
    except MALFORMED_EXCEPTIONS as exc:
        _exit_malformed(exc)
    typer.echo(f"initialized: {ledger.ledger_dir}")


@app.command()
def record(
    path: Path,
    event_type: str = typer.Option(..., "--type", help="Event type, such as claim."),
) -> None:
    """Record a research event for a local file."""
    try:
        event = Ledger(Path.cwd()).record(path, event_type=event_type)
    except (ValueError, TimeoutError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2) from exc
    except MALFORMED_EXCEPTIONS as exc:
        _exit_malformed(exc)
    typer.echo(f"recorded: {event.event_id} {event.event_hash}")


@app.command("delete")
def delete_event(
    path: Path,
    reason: Optional[str] = typer.Option(None, "--reason", help="Reason for deleting this path."),
) -> None:
    """Record that a working note path was intentionally deleted."""
    metadata = {"reason": reason} if reason else {}
    try:
        event = Ledger(Path.cwd()).record_delete(path, metadata=metadata)
    except (ValueError, TimeoutError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2) from exc
    except MALFORMED_EXCEPTIONS as exc:
        _exit_malformed(exc)
    typer.echo(f"recorded delete: {event.event_id} {event.event_hash}")


@app.command("rename")
def rename_event(
    old_path: Path,
    new_path: Path,
    reason: Optional[str] = typer.Option(None, "--reason", help="Reason for renaming this path."),
) -> None:
    """Record that a working note path was intentionally renamed."""
    metadata = {"reason": reason} if reason else {}
    try:
        event = Ledger(Path.cwd()).record_rename(old_path, new_path, metadata=metadata)
    except (ValueError, TimeoutError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2) from exc
    except MALFORMED_EXCEPTIONS as exc:
        _exit_malformed(exc)
    typer.echo(f"recorded rename: {event.event_id} {event.event_hash}")


@app.command()
def seal(label: str = typer.Option("seal", "--label", help="Human-readable seal label.")) -> None:
    """Create a Merkle-root seal for current events."""
    try:
        seal_result = Ledger(Path.cwd()).seal(label=label)
    except (ValueError, TimeoutError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2) from exc
    except MALFORMED_EXCEPTIONS as exc:
        _exit_malformed(exc)
    typer.echo(f"sealed: {seal_result.event_count} events {seal_result.merkle_root}")


@app.command()
def verify(
    no_working_tree: bool = typer.Option(
        False,
        "--no-working-tree",
        help="Skip mutable working-file drift checks for audit bundles.",
    ),
) -> None:
    """Verify ledger integrity."""
    try:
        result = Ledger(Path.cwd()).verify(check_working_files=not no_working_tree)
    except MALFORMED_EXCEPTIONS as exc:
        _exit_malformed(exc)
    for warning in result.warnings:
        typer.echo(warning, err=True)
    if result.ok:
        if result.warnings:
            raise typer.Exit(1)
        typer.echo(f"ok: {result.event_count} events verified")
        return
    for issue in result.issues:
        typer.echo(issue, err=True)
    if ISSUE_MALFORMED in result.issue_codes:
        raise typer.Exit(3)
    if ISSUE_SNAPSHOT_MISSING in result.issue_codes:
        raise typer.Exit(4)
    raise typer.Exit(2)


@app.command("export-bundle")
def export_bundle(
    output: Path = typer.Option(..., "--output", "-o", help="Write audit bundle ZIP here."),
) -> None:
    """Export a third-party verification bundle without private key material."""
    try:
        bundle_path = export_audit_bundle(Ledger(Path.cwd()), output)
    except (ValueError, TimeoutError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2) from exc
    except MALFORMED_EXCEPTIONS as exc:
        _exit_malformed(exc)
    typer.echo(f"wrote: {bundle_path}")


@app.command()
def report() -> None:
    """Print a short ledger status report."""
    try:
        ledger = Ledger(Path.cwd())
        events = ledger.events()
        result = ledger.verify()
    except MALFORMED_EXCEPTIONS as exc:
        _exit_malformed(exc)
    seals = list(ledger.seals_dir.glob("*.json"))
    typer.echo("Research Ledger Report")
    typer.echo(f"events: {len(events)}")
    typer.echo(f"seals: {len(seals)}")
    if result.ok and result.warnings:
        status = "warning"
    else:
        status = "ok" if result.ok else "failed"
    typer.echo(f"status: {status}")
    if events:
        typer.echo(f"tip: {events[-1].event_hash}")


@app.command()
def export_disclosure(
    output_format: Literal["markdown", "json"] = typer.Option(
        "markdown",
        "--format",
        help="Disclosure output format.",
    ),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Write report to file."),
) -> None:
    """Export an AI-use disclosure draft from the current ledger."""
    try:
        ledger = Ledger(Path.cwd())
        disclosure = build_disclosure_report(ledger)
    except MALFORMED_EXCEPTIONS as exc:
        _exit_malformed(exc)
    rendered = render_json(disclosure) if output_format == "json" else render_markdown(disclosure)
    if output:
        output.write_text(rendered, encoding="utf-8")
        typer.echo(f"wrote: {output}")
        return
    typer.echo(rendered)
