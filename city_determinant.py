import re
from urllib.parse import urlparse


SUPPORTED_CITIES = (
    "baltimore",
    "westvirginia",
    "hawaii",
    "dc",
    "pittsburgh",
    "philadelphia",
    "virtual",
)

_STATE_TO_CITY = {
    "DC": "dc",
    "DISTRICT OF COLUMBIA": "dc",
    "HI": "hawaii",
    "HAWAII": "hawaii",
    "WV": "westvirginia",
    "WEST VIRGINIA": "westvirginia",
}

_CITY_ALIASES = {
    "baltimore": {
        "baltimore",
        "bmore",
        "catonsville",
        "towson",
        "owings mills",
        "columbia md",
        "maryland",
    },
    "dc": {
        "washington dc",
        "washington d.c.",
        "district of columbia",
        "d.c.",
        "bethesda",
        "arlington",
        "alexandria",
        "silver spring",
        "georgetown",
    },
    "pittsburgh": {
        "pittsburgh",
        "pgh",
        "allegheny",
    },
    "philadelphia": {
        "philadelphia",
        "philly",
        "center city",
        "fishtown",
    },
    "hawaii": {
        "hawaii",
        "honolulu",
        "oahu",
        "maui",
        "kauai",
        "hilo",
        "kona",
    },
    "westvirginia": {
        "west virginia",
        "charleston wv",
        "morgantown",
        "huntington wv",
        "wheeling",
        "martinsburg",
    },
}

_VIRTUAL_KEYWORDS = {
    "virtual",
    "online",
    "remote",
    "webinar",
    "livestream",
    "zoom",
    "google meet",
    "meet.google.com",
    "teams meeting",
    "discord",
}

_DC_SHORT_TOKEN_PATTERN = re.compile(r"\bdc\b")
_WV_SHORT_TOKEN_PATTERN = re.compile(r"\bwv\b")


def _normalize_text(value):
    text = str(value or "").strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def _all_event_text(event):
    location = event.get("location") or {}
    fields = [
        event.get("name"),
        event.get("description"),
        event.get("source_group"),
        event.get("group"),
        event.get("url"),
        event.get("source"),
        event.get("source_url"),
        location.get("name") if isinstance(location, dict) else "",
        location.get("address") if isinstance(location, dict) else "",
        location.get("city") if isinstance(location, dict) else "",
        location.get("state") if isinstance(location, dict) else "",
        location.get("country") if isinstance(location, dict) else "",
    ]
    return _normalize_text(" ".join(str(field or "") for field in fields))


def _location_city_state_signal(location):
    if not isinstance(location, dict):
        return None, []
    city = _normalize_text(location.get("city"))
    state = str(location.get("state") or "").strip().upper()
    reasons = []

    city_map = {
        "baltimore": "baltimore",
        "washington": "dc",
        "washington dc": "dc",
        "washington d.c.": "dc",
        "district of columbia": "dc",
        "pittsburgh": "pittsburgh",
        "philadelphia": "philadelphia",
        "philly": "philadelphia",
        "honolulu": "hawaii",
        "charleston": "westvirginia",
        "morgantown": "westvirginia",
        "huntington": "westvirginia",
        "wheeling": "westvirginia",
    }

    if city in city_map:
        mapped = city_map[city]
        reasons.append(f"location.city={city}")
        if city == "washington" and state and state not in {"DC", "DISTRICT OF COLUMBIA"}:
            # Washington could be a non-DC city; require stronger signal via state.
            mapped = None
        if city in {"charleston"} and state and state != "WV":
            mapped = None
        if mapped:
            return mapped, reasons

    mapped_state = _STATE_TO_CITY.get(state) or _STATE_TO_CITY.get(state.replace(".", ""))
    if mapped_state:
        reasons.append(f"location.state={state}")
        return mapped_state, reasons

    return None, reasons


def _score_alias_matches(full_text, allowed):
    scores = {city: 0 for city in allowed}
    reasons = {city: [] for city in allowed}

    for city, aliases in _CITY_ALIASES.items():
        if city not in scores:
            continue
        for alias in aliases:
            if alias in full_text:
                scores[city] += 24
                reasons[city].append(f"text_alias:{alias}")

    if "dc" in scores and _DC_SHORT_TOKEN_PATTERN.search(full_text):
        scores["dc"] += 18
        reasons["dc"].append("token:dc")

    if "westvirginia" in scores and _WV_SHORT_TOKEN_PATTERN.search(full_text):
        scores["westvirginia"] += 14
        reasons["westvirginia"].append("token:wv")

    return scores, reasons


def _score_url_signals(event, allowed):
    scores = {city: 0 for city in allowed}
    reasons = {city: [] for city in allowed}
    urls = [
        str(event.get("url") or ""),
        str(event.get("source") or ""),
        str(event.get("source_url") or ""),
    ]
    lowered = " ".join(url.lower() for url in urls if url)

    url_hints = {
        "baltimore": ("baltimore", "bmore"),
        "dc": ("washington-dc", "dc-", "district-of-columbia"),
        "pittsburgh": ("pittsburgh", "pgh"),
        "philadelphia": ("philadelphia", "philly"),
        "hawaii": ("hawaii", "honolulu", "oahu"),
        "westvirginia": ("west-virginia", "westvirginia", "/wv"),
    }
    for city, hints in url_hints.items():
        if city not in scores:
            continue
        for hint in hints:
            if hint in lowered:
                scores[city] += 20
                reasons[city].append(f"url_hint:{hint}")

    for raw_url in urls:
        parsed = urlparse(raw_url)
        host = parsed.netloc.lower()
        if "hawaii" in host and "hawaii" in scores:
            scores["hawaii"] += 16
            reasons["hawaii"].append(f"host:{host}")
        if "wv" in host and "westvirginia" in scores:
            scores["westvirginia"] += 14
            reasons["westvirginia"].append(f"host:{host}")

    return scores, reasons


def _is_virtual_event(event, full_text):
    location = event.get("location") or {}
    location_text = _normalize_text(
        " ".join(
            [
                str(location.get("name") or ""),
                str(location.get("address") or ""),
                str(location.get("city") or ""),
                str(location.get("state") or ""),
            ]
        )
    )
    if any(keyword in full_text for keyword in _VIRTUAL_KEYWORDS):
        if " in person" not in full_text:
            return True
    if location_text in {"online", "virtual", "remote", "online event", "virtual event"}:
        return True
    return False


def determine_event_city(event, cities=None, fallback_city=None):
    allowed = tuple(city for city in (cities or SUPPORTED_CITIES) if city in SUPPORTED_CITIES)
    if not allowed:
        return {"city": fallback_city, "confidence": "none", "score": 0, "scores": {}, "reasons": []}

    full_text = _all_event_text(event)
    scores = {city: 0 for city in allowed}
    reasons = {city: [] for city in allowed}

    location_city, location_reasons = _location_city_state_signal(event.get("location") or {})
    if location_city in scores:
        scores[location_city] += 120
        reasons[location_city].extend(location_reasons)

    alias_scores, alias_reasons = _score_alias_matches(full_text, allowed)
    for city in allowed:
        scores[city] += alias_scores[city]
        reasons[city].extend(alias_reasons[city])

    url_scores, url_reasons = _score_url_signals(event, allowed)
    for city in allowed:
        scores[city] += url_scores[city]
        reasons[city].extend(url_reasons[city])

    if "virtual" in scores and _is_virtual_event(event, full_text):
        physical_peak = max((scores[city] for city in scores if city != "virtual"), default=0)
        if physical_peak < 120:
            scores["virtual"] += 130
            reasons["virtual"].append("virtual_signal")

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    top_city, top_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0

    if top_score <= 0:
        return {
            "city": fallback_city if fallback_city in allowed else None,
            "confidence": "none",
            "score": top_score,
            "scores": scores,
            "reasons": [],
        }

    if top_score < 60 and fallback_city in allowed:
        return {
            "city": fallback_city,
            "confidence": "low",
            "score": top_score,
            "scores": scores,
            "reasons": reasons.get(top_city, []),
        }

    if top_score < 120 and (top_score - second_score) <= 14:
        return {
            "city": None,
            "confidence": "none",
            "score": top_score,
            "scores": scores,
            "reasons": reasons.get(top_city, []),
        }

    confidence = "low"
    if top_score >= 120:
        confidence = "high"
    elif top_score >= 60:
        confidence = "medium"

    return {
        "city": top_city,
        "confidence": confidence,
        "score": top_score,
        "scores": scores,
        "reasons": reasons.get(top_city, []),
    }
