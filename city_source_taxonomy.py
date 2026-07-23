_MASLOW_BY_TAG = {
    "Food": ["Food"],
    "Water": ["Water"],
    "Water & Environment": ["Water"],
    "Housing": ["Shelter", "Safety"],
    "Shelter + Habitat": ["Shelter"],
    "Clothing": ["Clothing"],
    "Survival & Health": ["Health"],
    "Wellness": ["Health"],
    "Health": ["Health"],
    "Health & Wellness": ["Health"],
    "Safety & Stability": ["Safety"],
    "Infrastructure": ["Safety"],
    "Finance": ["Safety"],
    "Climate & Energy": ["Safety"],
    "Climate": ["Safety"],
    "Energy": ["Safety"],
    "Belonging & Culture": ["Belonging"],
    "Culture": ["Belonging"],
    "Community": ["Belonging"],
    "Religion": ["Belonging"],
    "Community Organizing": ["Belonging", "Purpose"],
    "Tech Community": ["Belonging"],
    "Code Collective & Partners": ["Belonging"],
    "Esteem & Opportunity": ["Esteem"],
    "Economic Development": ["Esteem"],
    "Economics": ["Esteem"],
    "Business": ["Esteem"],
    "Startup": ["Esteem"],
    "Entrepreneurship": ["Esteem"],
    "Career Growth": ["Esteem"],
    "Professional Networking": ["Esteem"],
    "Growth & Creativity": ["Growth"],
    "Tech Skills": ["Growth"],
    "Education": ["Growth"],
    "Science": ["Growth"],
    "Lifelong Learning": ["Growth"],
    "Youth Education": ["Growth"],
    "Makerspace": ["Growth"],
    "AI": ["Growth"],
    "Data Science": ["Growth"],
    "Cybersecurity": ["Growth"],
    "Cloud & Platform": ["Growth"],
    "DevOps": ["Growth"],
    "Software Development": ["Growth"],
    "Web Development": ["Growth"],
    "JavaScript": ["Growth"],
    "Python": ["Growth"],
    "Ruby": ["Growth"],
    "Product": ["Growth"],
    "UX": ["Growth"],
    "Game Development": ["Growth"],
    "Technical Writing": ["Growth"],
    "Open Source": ["Growth"],
    "Robotics": ["Growth"],
    "Purpose & Service": ["Purpose"],
    "Politics": ["Purpose"],
    "Faith & Spirituality": ["Purpose"],
    "Civic Tech": ["Purpose"],
    "Policy": ["Purpose"],
    "Crypto & Web3": ["Safety"],
}

_MASLOW_DEFAULT = "Belonging"

_COMMUNITY_SECTOR_BY_TAG = {
    "Technology": "Technology",
    "Tech Skills": "Technology",
    "Growth & Creativity": "Technology",
    "AI": "Technology",
    "Data Science": "Technology",
    "Cybersecurity": "Technology",
    "Cloud & Platform": "Technology",
    "DevOps": "Technology",
    "Software Development": "Technology",
    "Web Development": "Technology",
    "JavaScript": "Technology",
    "Python": "Technology",
    "Ruby": "Technology",
    "Product": "Technology",
    "UX": "Technology",
    "Game Development": "Technology",
    "Technical Writing": "Technology",
    "Open Source": "Technology",
    "Tech Community": "Technology",
    "Education": "Education",
    "Science": "Education",
    "Lifelong Learning": "Education",
    "Youth Education": "Education",
    "Entrepreneurship": "Entrepreneurship",
    "Business": "Entrepreneurship",
    "Startup": "Entrepreneurship",
    "Career Growth": "Entrepreneurship",
    "Professional Networking": "Entrepreneurship",
    "Economics": "Economics",
    "Economic Development": "Economics",
    "Esteem & Opportunity": "Economics",
    "Finance": "Finance",
    "Crypto & Web3": "Finance",
    "Health": "Health",
    "Wellness": "Health",
    "Health & Wellness": "Health",
    "Survival & Health": "Health",
    "Politics": "Politics",
    "Civic Tech": "Politics",
    "Policy": "Politics",
    "Purpose & Service": "Politics",
    "Culture": "Culture",
    "Belonging & Culture": "Culture",
    "Community": "Culture",
    "Community Organizing": "Culture",
    "Code Collective & Partners": "Culture",
    "Religion": "Faith",
    "Faith & Spirituality": "Faith",
    "Water": "Environment",
    "Water & Environment": "Environment",
    "Climate": "Environment",
    "Climate & Energy": "Environment",
    "Energy": "Environment",
    "Infrastructure": "Environment",
    "Safety & Stability": "Environment",
    "Makerspace": "Makerspace",
    "Robotics": "Makerspace",
    "Other": "Other",
}


def filter_excluded_org_tags(tags, excluded_org_tags):
    """Remove organization-inherited tags for explicitly excluded sectors.

    Exclusions may name either a concrete tag or a community-sector label.  A
    sector exclusion also removes source tags that map to that sector so, for
    example, excluding ``Environment`` removes both ``Environment`` and
    ``Infrastructure`` before the source tags are inherited by every event.
    Event-specific tags added by a scraper remain untouched.
    """
    if not isinstance(excluded_org_tags, list) or not excluded_org_tags:
        return list(tags or [])

    excluded = {
        str(tag or "").strip().casefold()
        for tag in excluded_org_tags
        if str(tag or "").strip()
    }
    filtered = []
    for tag in tags or []:
        normalized_tag = str(tag or "").strip()
        mapped_sector = _COMMUNITY_SECTOR_BY_TAG.get(normalized_tag, "")
        if normalized_tag.casefold() in excluded:
            continue
        if mapped_sector.casefold() in excluded:
            continue
        filtered.append(tag)
    return filtered


def _append_community_sector_tags(source):
    tags = list(source.get("tags") or [])
    seen = set(tags)
    sector_tags = []
    for tag in tags:
        mapped = _COMMUNITY_SECTOR_BY_TAG.get(tag)
        if mapped and mapped not in seen:
            seen.add(mapped)
            sector_tags.append(mapped)
    if sector_tags:
        source["tags"] = tags + sector_tags


def _append_maslow_tags(source):
    tags = list(source.get("tags") or [])
    seen = set(tags)
    maslow_tags = []
    for tag in tags:
        for mapped in _MASLOW_BY_TAG.get(tag, []):
            if mapped in seen:
                continue
            seen.add(mapped)
            maslow_tags.append(mapped)
    if not maslow_tags and _MASLOW_DEFAULT not in seen:
        maslow_tags.append(_MASLOW_DEFAULT)
    if maslow_tags:
        source["tags"] = tags + maslow_tags


def apply_city_source_taxonomy(sources):
    for source in sources:
        _append_community_sector_tags(source)
        _append_maslow_tags(source)
        source["tags"] = filter_excluded_org_tags(
            source.get("tags"),
            source.get("excluded_org_tags"),
        )
