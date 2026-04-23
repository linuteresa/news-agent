from datetime import datetime, timezone, timedelta
import time

def is_recent(entry, hours=24):

    for date_attr in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, date_attr, None)
        if parsed:
            pub_time = datetime.fromtimestamp(time.mktime(parsed), tz=timezone.utc)
            cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=hours)
            return pub_time >= cutoff
    return True
import re

def normalize_title(title):
    """Lowercase, strip punctuation for fuzzy comparison."""
    return re.sub(r'[^a-z0-9 ]', '', title.lower()).strip()

def deduplicate_articles(articles_by_source):
    """
    articles_by_source: dict of { source_name: [entries] }
    Returns same structure but with cross-source duplicates removed.
    Keeps the first occurrence (prioritizes sources in insertion order).
    """
    seen_words = []  # list of word-sets from seen titles

    def is_duplicate(title):
        words = set(normalize_title(title).split())
        if len(words) < 3:
            return False
        for seen in seen_words:
            overlap = len(words & seen) / max(len(words), len(seen))
            if overlap > 0.6:   # 60% word overlap = duplicate
                return True
        seen_words.append(words)
        return False

    result = {}
    for source, entries in articles_by_source.items():
        unique = [e for e in entries if not is_duplicate(e.title)]
        if unique:
            result[source] = unique
    return result