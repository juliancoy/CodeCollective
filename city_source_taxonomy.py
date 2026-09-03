def normalize_tags(tags):
    """Trim and deduplicate tags without interpreting their meaning."""
    normalized = []
    seen = set()
    for tag in tags or []:
        value = str(tag or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return normalized


def apply_city_source_taxonomy(sources):
    """Compatibility shim: source files are authoritative.

    No category, sector, Maslow, or exclusion expansion happens here.
    """
    for source in sources or []:
        source["tags"] = normalize_tags(source.get("tags"))
    return sources
