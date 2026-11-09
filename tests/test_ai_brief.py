import json
import os
import sys
import time
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import ai_brief
from helper import deduplicate_articles

NOW = time.gmtime()
OLD = time.gmtime(time.time() - 3 * 24 * 3600)


def entry(title, link, desc="", when=NOW):
    return SimpleNamespace(title=title, link=link, description=desc, published_parsed=when)


NEWS = {
    "Lab": [
        entry("New frontier model released with longer context", "https://lab.example/model", "Big release."),
        entry("Old story from last week about chips", "https://lab.example/old", when=OLD),
    ],
    "Blog": [
        entry("Open-weight model tops coding leaderboard", "https://blog.example/open", "Open weights."),
        entry("New frontier model released with longer context", "https://blog.example/dupe"),  # same title
    ],
}
PAPERS = {
    "arXiv": [
        entry("Weight-Space Programming at Scale", "https://arxiv.org/abs/1", "Announce Type: new Abstract: ..."),
        entry("A revised paper", "https://arxiv.org/abs/2", "Announce Type: replace Abstract: ..."),
    ],
}
FEEDS = {**NEWS, **PAPERS}


def fake_parse(url):
    if url == "broken":
        raise RuntimeError("feed down")
    return SimpleNamespace(entries=FEEDS[url])


def collect():
    return ai_brief.collect_items(
        news_feeds={"Lab": "Lab", "Blog": "Blog", "Broken": "broken"},
        paper_feeds={"arXiv": "arXiv"},
        parse=fake_parse,
    )


def use_fake_feeds(monkeypatch, news=None, papers=None):
    monkeypatch.setattr(ai_brief, "AI_NEWS_FEEDS", {"Lab": "Lab", "Blog": "Blog"} if news is None else news)
    monkeypatch.setattr(ai_brief, "PAPER_FEEDS", {"arXiv": "arXiv"} if papers is None else papers)


class FakeClient:
    def __init__(self, text=None, error=None):
        self.text, self.error, self.calls = text, error, 0
        self.models = self

    def generate_content(self, model, contents, config=None):
        self.calls += 1
        if self.error:
            raise self.error
        return SimpleNamespace(text=self.text)


def test_collect_filters_old_duplicate_revised_and_survives_broken_feed():
    items = collect()
    titles = [it["title"] for it in items]
    assert titles == [
        "New frontier model released with longer context",
        "Open-weight model tops coding leaderboard",
        "Weight-Space Programming at Scale",
    ]
    assert [it["id"] for it in items] == [1, 2, 3]
    assert items[2]["kind"] == "paper"


def good_json(**overrides):
    data = {
        "quiet_day": False,
        "top_stories": [{"id": 1, "headline": "Frontier model ships", "what_happened": "A lab shipped a model.",
                         "why_it_matters": "Longer context <helps> agents."}],
        "quick_hits": [{"id": 2, "summary": "Open model leads coding."}, {"id": 1, "summary": "dupe of top"},
                       {"id": 99, "summary": "invented item"}],
        "paper_of_the_day": {"id": 3, "explanation": "LLMs edit weights directly."},
        "concept_to_learn": {"term": "Context window", "explanation": "How much text a model can read at once."},
    }
    data.update(overrides)
    return json.dumps(data)


def test_parse_brief_drops_unknown_ids_and_repeats():
    items = collect()
    brief = ai_brief.parse_brief(good_json(), items)
    assert [s["id"] for s in brief["top_stories"]] == [1]
    assert [h["id"] for h in brief["quick_hits"]] == [2]  # dupe of top story and invented id 99 removed
    assert brief["paper_of_the_day"]["id"] == 3


def test_paper_of_the_day_must_be_a_paper():
    items = collect()
    brief = ai_brief.parse_brief(good_json(paper_of_the_day={"id": 1, "explanation": "x"}), items)
    assert brief["paper_of_the_day"] is None


def test_parse_brief_accepts_code_fenced_json():
    items = collect()
    brief = ai_brief.parse_brief("```json\n" + good_json() + "\n```", items)
    assert brief["top_stories"]


def test_full_flow_with_fakes(monkeypatch):
    use_fake_feeds(monkeypatch)
    client = FakeClient(text=good_json())
    out, items = ai_brief.get_ai_brief(client, "m", parse=fake_parse)
    assert client.calls == 1
    assert "Daily AI Brief" in out
    assert 'href="https://lab.example/model"' in out
    assert 'href="https://arxiv.org/abs/1"' in out
    assert "&lt;helps&gt;" in out and "<helps>" not in out
    assert "invented item" not in out
    assert "Concept to learn: Context window" in out


def test_fallback_when_gemini_fails(monkeypatch):
    use_fake_feeds(monkeypatch)
    out, _ = ai_brief.get_ai_brief(FakeClient(error=RuntimeError("quota")), "m", parse=fake_parse)
    assert "Summaries were unavailable" in out
    assert 'href="https://lab.example/model"' in out


def test_fallback_when_gemini_returns_bad_json(monkeypatch):
    use_fake_feeds(monkeypatch)
    out, _ = ai_brief.get_ai_brief(FakeClient(text="not json"), "m", parse=fake_parse)
    assert "Summaries were unavailable" in out


def test_no_items_means_no_section_and_no_gemini_call(monkeypatch):
    use_fake_feeds(monkeypatch, news={}, papers={})
    client = FakeClient(text=good_json())
    out, items = ai_brief.get_ai_brief(client, "m", parse=fake_parse)
    assert out == "" and items == [] and client.calls == 0


def test_tech_section_skips_stories_already_in_ai_brief():
    tech = {"TechCrunch": [entry("New frontier model released with longer context!", "https://tc.example/a"),
                           entry("Phone maker announces foldable", "https://tc.example/b")]}
    result = deduplicate_articles(tech, ["New frontier model released with longer context"])
    assert [e.title for e in result["TechCrunch"]] == ["Phone maker announces foldable"]


def test_dedup_still_works_without_seen_titles():
    tech = {"A": [entry("Big chip deal announced today", "x")], "B": [entry("Big chip deal announced today", "y")]}
    assert list(deduplicate_articles(tech)) == ["A"]
