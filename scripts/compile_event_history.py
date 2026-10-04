#!/usr/bin/env python3
"""Compile both Baltimore event-file paths across all available Git history.

Run: python3 scripts/compile_event_history.py
Output is a normal event array; a companion report records coverage and provenance.
Uniqueness means URL + start instant, or name + start instant without a URL.
Different dates of a recurring event remain separate. The newest committed
record wins when descriptions, tags, images, or other details change.
Only locally available refs are read; no fetch or working-tree edits are made.
"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import unicodedata


PATHS = ("upcoming_events.json", "baltimore/upcoming_events.json")


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True)


def identity(event):
    start = str(event.get("startDate") or "").strip()
    try:
        parsed = datetime.fromisoformat(start.replace("Z", "+00:00"))
        if parsed.tzinfo:
            start = parsed.astimezone(timezone.utc).isoformat()
    except ValueError:
        pass
    url = str(event.get("url") or "").strip()
    name = " ".join(unicodedata.normalize("NFKC", str(event.get("name") or "")).casefold().split())
    if start and (url or name):
        return ("url" if url else "name", url or name, start)
    # Do not collapse undated or unidentified records into one event.
    return ("record", json.dumps({k: v for k, v in event.items() if k != "scrapeTime"}, sort_keys=True, ensure_ascii=False))


def read_records(raw):
    try:
        return json.loads(raw), False
    except json.JSONDecodeError:
        lines = raw.decode().splitlines(keepends=True)
        if not any(line.startswith("<<<<<<< ") for line in lines):
            raise
        # Parse each complete conflict resolution independently, preserving both
        # alternatives. Never strip all markers and concatenate object fragments.
        alternatives = []
        for side in ("ours", "theirs"):
            section = "shared"
            resolved = []
            for line in lines:
                if line.startswith("<<<<<<< "):
                    section = "ours"
                elif line.startswith("||||||| "):
                    section = "base"
                elif line.startswith("======="):
                    section = "theirs"
                elif line.startswith(">>>>>>> "):
                    section = "shared"
                elif section in ("shared", side):
                    resolved.append(line)
            records = json.loads("".join(resolved))
            if not isinstance(records, list):
                raise ValueError("Conflict resolution is not an event array")
            alternatives.extend(records)
        return alternatives, True


def compile_history(repo, output):
    if git(repo, "rev-parse", "--is-shallow-repository").strip() == "true":
        raise ValueError("This is a shallow checkout; unshallow it before compiling full history.")
    log = git(repo, "log", "--all", "--full-history", "--reverse", "--topo-order", "-m", "--raw", "--no-renames",
              "--no-abbrev", "--format=COMMIT %ct %H", "--", *PATHS)
    snapshots = {}
    first_snapshot = {}
    commits = set()
    sequence = 0
    for line in log.splitlines():
        if line.startswith("COMMIT "):
            _, timestamp, commit = line.split()
            sequence += 1
        elif line.startswith(":"):
            fields, path = line.split("\t", 1)
            blob = fields.split()[3]
            if set(blob) == {"0"}:
                continue  # deletion; previous versions are covered by full history
            commits.add(commit)
            rank = (int(timestamp), sequence, commit, PATHS.index(path))
            first_snapshot[blob] = min(first_snapshot.get(blob, rank), rank)
            if blob not in snapshots or rank > snapshots[blob][0]:
                snapshots[blob] = (rank, path)
    events = {}
    provenance = {}
    first_seen = {}
    total = 0
    non_event_entries = []
    recovered_conflicts = []
    batch = subprocess.Popen(["git", "-C", str(repo), "cat-file", "--batch"],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    try:
        for blob, (rank, path) in sorted(snapshots.items(), key=lambda item: item[1][0]):
            batch.stdin.write((blob + "\n").encode())
            batch.stdin.flush()
            header = batch.stdout.readline().decode().split()
            if len(header) != 3 or header[1] != "blob":
                raise ValueError(f"Cannot read blob {blob}: {header}")
            raw = batch.stdout.read(int(header[2]))
            batch.stdout.read(1)
            try:
                records, recovered = read_records(raw)
                if recovered:
                    recovered_conflicts.append({"commit": rank[2], "path": path, "blob": blob})
                if not isinstance(records, list):
                    raise ValueError("Expected an array of event objects")
            except (ValueError, UnicodeDecodeError) as error:
                raise ValueError(f"Invalid historical JSON at {rank[2]}:{path}: {error}") from error
            total += len(records)
            for index, event in enumerate(records):
                if not isinstance(event, dict):
                    non_event_entries.append({"commit": rank[2], "path": path,
                                              "index": index, "value": event})
                    continue
                key = identity(event)
                events[key] = event
                first_seen[key] = min(first_seen.get(key, first_snapshot[blob]), first_snapshot[blob])
                provenance[key] = {
                    "first_seen_commit": first_seen[key][2],
                    "latest_record_commit": rank[2], "latest_record_path": path,
                }
    finally:
        batch.stdin.close()
        batch.stdout.close()
        batch.wait()
    ordered = sorted(events, key=lambda key: (str(events[key].get("startDate") or ""),
                                             str(events[key].get("name") or ""), key))
    report = {
        "paths": list(PATHS), "refs": git(repo, "show-ref").splitlines(),
        "commits_with_snapshots": len(commits), "unique_json_blobs": len(snapshots),
        "event_records_read": total, "unique_events": len(events),
        "deduplication": "URL and normalized start instant; name and start instant if URL absent; newest commit wins",
        "coverage": "All local refs, including remote-tracking refs; committed files only. No network fetch.",
        "non_event_entries": non_event_entries,
        "recovered_conflicts": recovered_conflicts,
        "events": [dict(output_index=i, **provenance[key]) for i, key in enumerate(ordered)],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps([events[key] for key in ordered], ensure_ascii=False, indent=2) + "\n")
    report_path = output.with_suffix(".report.json")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(f"Read {total:,} records from {len(snapshots):,} distinct snapshots; wrote {len(events):,} unique events to {output}")
    print(f"Coverage and per-event provenance: {report_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, help="Defaults to baltimore/event_history.json in the repository")
    args = parser.parse_args()
    compile_history(args.repo, args.output or args.repo / "baltimore/event_history.json")
