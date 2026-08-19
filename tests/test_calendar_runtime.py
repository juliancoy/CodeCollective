import threading
import time

import genCalendar
import run_calendar


def test_bounded_fetch_all_sources_enforces_global_and_kind_limits(monkeypatch):
    active = 0
    max_active = 0
    active_by_kind = {}
    max_by_kind = {}
    lock = threading.Lock()

    monkeypatch.setattr(
        genCalendar,
        "SOURCE_KIND_CONCURRENCY",
        {"meetup": 1, "luma_event": 2, "unknown": 1},
    )

    def fake_fetch(source, city):
        nonlocal active, max_active
        kind = source["source_kind"]
        with lock:
            active += 1
            active_by_kind[kind] = active_by_kind.get(kind, 0) + 1
            max_active = max(max_active, active)
            max_by_kind[kind] = max(
                max_by_kind.get(kind, 0), active_by_kind[kind]
            )
        time.sleep(0.01)
        with lock:
            active -= 1
            active_by_kind[kind] -= 1
        return [{"name": source["url"]}], [], []

    monkeypatch.setattr(genCalendar, "fetch_events_from_source", fake_fetch)

    sources = [
        {"url": f"https://meetup.example/{i}", "source_kind": "meetup"}
        for i in range(5)
    ] + [
        {"url": f"https://luma.example/{i}", "source_kind": "luma_event"}
        for i in range(5)
    ]

    events, unmatched, errors = run_calendar.bounded_fetch_all_sources(
        sources, "baltimore", max_workers=3
    )

    assert len(events) == len(sources)
    assert unmatched == []
    assert errors == []
    assert max_active <= 3
    assert max_by_kind["meetup"] <= 1
    assert max_by_kind["luma_event"] <= 2
