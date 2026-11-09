"""
Daily AI Brief: a learner-friendly digest of the last day's AI news.

Pulls AI-focused feeds (lab blogs, AI news, arXiv), then makes ONE Gemini call
that picks the top stories, quick hits, a paper of the day and a concept to
learn. Gemini only returns item IDs plus its own wording; every link in the
email comes from the feeds themselves, so it can't invent sources.
"""
import html
import json
import re

import feedparser

from helper import is_recent, normalize_title

AI_NEWS_FEEDS = {
    "OpenAI": "https://openai.com/news/rss.xml",
    "Google DeepMind": "https://deepmind.google/blog/rss.xml",
    "Hugging Face": "https://huggingface.co/blog/feed.xml",
    "MIT Technology Review": "https://www.technologyreview.com/topic/artificial-intelligence/feed",
    "TechCrunch AI": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "VentureBeat AI": "https://venturebeat.com/category/ai/feed/",
    "The Decoder": "https://the-decoder.com/feed/",
    "Simon Willison": "https://simonwillison.net/atom/everything/",
}

PAPER_FEEDS = {
    "arXiv cs.AI": "https://rss.arxiv.org/rss/cs.AI",
    "arXiv cs.CL": "https://rss.arxiv.org/rss/cs.CL",
    "arXiv cs.LG": "https://rss.arxiv.org/rss/cs.LG",
}

MAX_PER_NEWS_SOURCE = 8
MAX_PAPERS_PER_FEED = 25
DESC_CHARS = 400


def _clean(text):
    """Strip HTML tags and collapse whitespace."""
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _is_new_arxiv_paper(entry):
    """arXiv feeds also list revised and cross-listed papers; keep only new ones."""
    desc = getattr(entry, "description", "") or ""
    match = re.search(r"Announce Type:\s*(\S+)", desc)
    return match is None or match.group(1).lower() == "new"


def collect_items(news_feeds=None, paper_feeds=None, hours=24, parse=feedparser.parse):
    """Fetch recent items from each feed. One broken feed never stops the others."""
    news_feeds = AI_NEWS_FEEDS if news_feeds is None else news_feeds
    paper_feeds = PAPER_FEEDS if paper_feeds is None else paper_feeds
    items = []
    seen_titles = set()

    def add(entry, source, kind):
        title = _clean(getattr(entry, "title", ""))
        link = getattr(entry, "link", "")
        key = normalize_title(title)
        if not title or not link or key in seen_titles:
            return
        seen_titles.add(key)
        items.append({
            "id": len(items) + 1,
            "kind": kind,
            "source": source,
            "title": title,
            "link": link,
            "description": _clean(getattr(entry, "description", ""))[:DESC_CHARS],
        })

    for source, url in news_feeds.items():
        try:
            feed = parse(url)
            recent = [e for e in feed.entries if is_recent(e, hours=hours)][:MAX_PER_NEWS_SOURCE]
            for entry in recent:
                add(entry, source, "news")
        except Exception as e:
            print(f"Error fetching {source}: {e}")

    for source, url in paper_feeds.items():
        try:
            feed = parse(url)
            new_papers = [e for e in feed.entries if is_recent(e, hours=hours) and _is_new_arxiv_paper(e)]
            for entry in new_papers[:MAX_PAPERS_PER_FEED]:
                add(entry, source, "paper")
        except Exception as e:
            print(f"Error fetching {source}: {e}")

    return items


def build_prompt(items):
    lines = [
        "You write a short daily AI brief for someone learning AI who wants to stay current.",
        "Below are today's AI news items and new research papers, each with an ID.",
        "Use ONLY these items. Never invent facts, numbers or stories that aren't in them.",
        "",
        "Return JSON with exactly this shape:",
        '{',
        '  "quiet_day": true or false (true if nothing significant happened),',
        '  "top_stories": [ up to 3 of the most important NEWS items:',
        '      {"id": <item id>, "headline": "<short headline>",',
        '       "what_happened": "<1-2 plain sentences>", "why_it_matters": "<1 sentence>"} ],',
        '  "quick_hits": [ 4 to 6 other notable items (news or papers), not repeating top stories:',
        '      {"id": <item id>, "summary": "<one line>"} ],',
        '  "paper_of_the_day": {"id": <id of one PAPER item, or null>,',
        '      "explanation": "<2-3 sentences: what it does and why it is interesting, for a learner>"},',
        '  "concept_to_learn": {"term": "<one AI term or idea that comes up in today\'s items>",',
        '      "explanation": "<2-3 plain sentences a learner can follow>"}',
        '}',
        "",
        "Prefer model releases, notable research, open-source tools, AI policy and safety,",
        "and big industry moves over minor product marketing. Write in plain English.",
        "",
        "ITEMS:",
    ]
    for it in items:
        lines.append(f"[{it['id']}] ({it['kind']}, {it['source']}) {it['title']} :: {it['description']}")
    return "\n".join(lines)


def parse_brief(raw_text, items):
    """Parse Gemini's JSON and drop anything pointing at an unknown item ID."""
    text = raw_text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    data = json.loads(text)
    by_id = {it["id"]: it for it in items}

    def valid(entry):
        return isinstance(entry, dict) and by_id.get(entry.get("id")) is not None

    top = [s for s in data.get("top_stories", []) if valid(s)][:3]
    top_ids = {s["id"] for s in top}
    hits = [h for h in data.get("quick_hits", []) if valid(h) and h["id"] not in top_ids][:6]

    paper = data.get("paper_of_the_day") or {}
    if not (valid(paper) and by_id[paper["id"]]["kind"] == "paper"):
        paper = None

    concept = data.get("concept_to_learn") or {}
    if not (concept.get("term") and concept.get("explanation")):
        concept = None

    return {
        "quiet_day": bool(data.get("quiet_day", False)),
        "top_stories": top,
        "quick_hits": hits,
        "paper_of_the_day": paper,
        "concept_to_learn": concept,
    }


# ---------- HTML rendering (inline styles, matching the rest of the email) ----------

H3 = 'style="font-size: 15px; color: #333; margin: 18px 0 8px 0;"'
P = 'style="color: #333; font-size: 14px; line-height: 1.5; margin: 0 0 6px 0;"'
LINK = 'style="text-decoration: none; color: #0056b3;"'


def _a(item, text=None):
    return f'<a href="{html.escape(item["link"], quote=True)}" {LINK}>{html.escape(text or item["title"])}</a>'


def render_brief(brief, items):
    by_id = {it["id"]: it for it in items}
    out = ['<h2 style="background-color: #e8f0fe; padding: 10px; border-radius: 5px; margin-top: 20px;">'
           '🧠 Daily AI Brief</h2>']

    if brief["quiet_day"]:
        out.append(f'<p {P}><em>A quiet day in AI. Here\'s what did come out.</em></p>')

    if brief["top_stories"]:
        out.append(f'<h3 {H3}>Top stories</h3>')
        for s in brief["top_stories"]:
            item = by_id[s["id"]]
            out.append(f"""
                <div style="margin-bottom: 16px;">
                    <p style="margin: 0 0 5px 0; font-size: 16px; line-height: 1.4;"><strong>{_a(item, s.get("headline"))}</strong>
                        <span style="color: #888; font-size: 12px;"> · {html.escape(item["source"])}</span></p>
                    <p {P}>{html.escape(s.get("what_happened", ""))}</p>
                    <p {P}><strong>Why it matters:</strong> {html.escape(s.get("why_it_matters", ""))}</p>
                </div>""")

    if brief["quick_hits"]:
        out.append(f'<h3 {H3}>Quick hits</h3><ul style="padding-left: 20px; margin: 0;">')
        for h in brief["quick_hits"]:
            item = by_id[h["id"]]
            out.append(f'<li style="color: #333; font-size: 14px; line-height: 1.5; margin-bottom: 6px;">'
                       f'{html.escape(h.get("summary", item["title"]))} ({_a(item, item["source"])})</li>')
        out.append('</ul>')

    paper = brief["paper_of_the_day"]
    if paper:
        item = by_id[paper["id"]]
        out.append(f'<h3 {H3}>📄 Paper of the day</h3>')
        out.append(f'<p style="margin: 0 0 5px 0; font-size: 15px;"><strong>{_a(item)}</strong></p>')
        out.append(f'<p {P}>{html.escape(paper.get("explanation", ""))}</p>')

    concept = brief["concept_to_learn"]
    if concept:
        out.append(f'<h3 {H3}>💡 Concept to learn: {html.escape(concept["term"])}</h3>')
        out.append(f'<p {P}>{html.escape(concept["explanation"])}</p>')

    return "\n".join(out)


def render_fallback(items, limit=8):
    """If Gemini fails, still send the headlines with links."""
    news = [it for it in items if it["kind"] == "news"][:limit]
    if not news:
        return ""
    rows = "".join(
        f'<li style="color: #333; font-size: 14px; line-height: 1.5; margin-bottom: 6px;">{_a(it)} '
        f'<span style="color: #888; font-size: 12px;">· {html.escape(it["source"])}</span></li>'
        for it in news
    )
    return ('<h2 style="background-color: #e8f0fe; padding: 10px; border-radius: 5px; margin-top: 20px;">'
            '🧠 Daily AI Brief</h2>'
            f'<p {P}><em>Summaries were unavailable today, so here are the headlines.</em></p>'
            f'<ul style="padding-left: 20px; margin: 0;">{rows}</ul>')


def get_ai_brief(client, model, hours=24, parse=feedparser.parse):
    """Returns (html, items). html is "" if there was nothing to report."""
    items = collect_items(hours=hours, parse=parse)
    if not items:
        print("⚠️ No AI items found for the brief.")
        return "", items

    print(f"🧠 Building AI brief from {len(items)} items...")
    try:
        response = client.models.generate_content(
            model=model,
            contents=build_prompt(items),
            config={"response_mime_type": "application/json"},
        )
        brief = parse_brief(response.text, items)
        if not (brief["top_stories"] or brief["quick_hits"]):
            raise ValueError("brief came back empty")
        return render_brief(brief, items), items
    except Exception as e:
        print(f"❌ AI brief error, falling back to headlines: {e}")
        return render_fallback(items), items
