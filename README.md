# news-agent
A agent to update you on current affairs

Every morning at 10:07 AM ET a Claude scheduled task starts the GitHub Actions workflow (`.github/workflows/manual.yml`) through the API, since GitHub's own cron ran hours late. It pulls RSS feeds, summarizes them with Gemini and emails one briefing with these sections:

- **🧠 Daily AI Brief** (`ai_brief.py`): top 3 AI stories with why each matters, quick hits, a paper of the day from arXiv, and one concept to learn. Sources: OpenAI, Google DeepMind, Hugging Face, MIT Technology Review, TechCrunch AI, VentureBeat AI, The Decoder, Simon Willison, and new arXiv papers in cs.AI, cs.CL and cs.LG. One Gemini call writes it and returns item IDs only, so every link comes from the feeds. Failed Gemini calls are retried (e.g. on 503 high demand); if they keep failing, the section falls back to plain headlines.
- **🚀 Tech**, **🏆 Sports**, **🌍 Global Affairs**: per-source one-line summaries. Tech skips stories the AI brief already covers.

Optional settings (env vars / repo secrets): `GEMINI_MODEL` (default `gemini-2.5-flash-lite`), `AI_BRIEF_ENABLED` (`false` turns the AI section off), `NUM_ARTICLES` (default 3).

Run the tests with `pip install pytest && pytest -q`.
