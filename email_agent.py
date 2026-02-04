import feedparser
import smtplib
from google import genai
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
import time

from config import GOOGLE_API_KEY, EMAIL_SENDER, EMAIL_PASSWORD, NUM_ARTICLES, get_email_receivers

RSS_CATEGORIES = {
    "🚀 Tech & AI": {
        "TechCrunch": "https://techcrunch.com/feed/",
        "The Verge": "https://www.theverge.com/rss/index.xml",
        "Hacker News": "https://news.ycombinator.com/rss",
        "Wired": "https://www.wired.com/feed/category/science/latest/rss"
    },
    "🏆 Sports": {
        "ESPN Top Headlines": "https://www.espn.com/espn/rss/news",
        "BBC Sport": "http://feeds.bbci.co.uk/sport/rss.xml"
    },
    "🌍 Global Affairs": {
        "BBC World": "http://feeds.bbci.co.uk/news/world/rss.xml",
        "NY Times (Top Stories)": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
        "Al Jazeera": "https://www.aljazeera.com/xml/rss/all.xml"
    }
}

client = genai.Client(api_key=GOOGLE_API_KEY)


def generate_batch_summaries(source_name, articles):
    """
    Sends ONE prompt containing multiple articles to save API calls.
    Returns a dictionary: { "Article Title": "Summary" }
    """
    if not articles:
        return {}


    prompt = f"""
    You are a news summarizer. I will give you {len(articles)} news items from {source_name}.
    Summarize each one into a single concise sentence.

    RETURN ONLY A LIST separated by "|||" (triple pipes) so I can split it later.
    Do not add bullet points or numbering. Just the summaries.
    Order them exactly as provided.

    Input Articles:
    """

    for i, art in enumerate(articles):

        clean_desc = (art.description[:500] if hasattr(art, 'description') else "")
        prompt += f"\nArticle {i + 1}: {art.title} - {clean_desc}\n"

    try:

        response = client.models.generate_content(
            model='gemini-2.5-flash-lite',
            contents=prompt
        )


        raw_text = response.text.strip()
        summaries_list = raw_text.split("|||")

        summaries_list = [s.strip() for s in summaries_list if s.strip()]

        result_map = {}
        for i, article in enumerate(articles):
            if i < len(summaries_list):
                result_map[article.title] = summaries_list[i]
            else:
                result_map[article.title] = "Summary unavailable."

        return result_map

    except Exception as e:
        print(f"❌ Batch Error for {source_name}: {e}")
        return {a.title: a.title for a in articles}


def get_summaries():
    briefing_content = ""

    for category, sources in RSS_CATEGORIES.items():
        if not sources: continue

        briefing_content += f"""<h2 style="background-color: #eee; padding: 10px; border-radius: 5px; margin-top: 20px;">{category}</h2>"""

        for source, url in sources.items():
            print(f"Processing {source} (Batching)...")

            try:
                feed = feedparser.parse(url)
                top_articles = feed.entries[:NUM_ARTICLES]

                if not top_articles:
                    continue

                summaries_map = generate_batch_summaries(source, top_articles)

                time.sleep(4)
                # ------------------------

                for article in top_articles:
                    summary = summaries_map.get(article.title, article.title)

                    briefing_content += f"""
                        <div style="margin-bottom: 20px;">
                            <p style="margin: 0 0 5px 0; font-size: 16px; line-height: 1.4;">
                                <strong><a href="{article.link}" style="text-decoration: none; color: #0056b3;"> {article.title}</a></strong>
                            </p>
                            <p style="color: #333; font-size: 14px; line-height: 1.5; margin: 0;">{summary}</p>
                        </div>
                    """
            except Exception as e:
                print(f"Error fetching feed for {source}: {e}")

    return briefing_content


def send_email(content):
    receivers = get_email_receivers()
    msg = MIMEMultipart("alternative")
    msg["From"] = "Linu's AI News Agent <" + EMAIL_SENDER + ">"
    msg["Subject"] = f"🌍 Morning Briefing: {datetime.now().strftime('%Y-%m-%d')}"
    msg["To"] = "You"

    html_body = f"""
    <html>
      <body style="font-family: Helvetica, Arial, sans-serif; background-color: #f4f4f4; margin: 0; padding: 20px;">
        <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; padding: 20px; border-radius: 10px;">
            <h1 style="color: #333; text-align: center; font-size: 24px;">Your Morning Briefing | TECH | SPORTS | GLOBAL AFFAIRS</h1>
            {content}
            <div style="margin-top: 40px; text-align: center; font-size: 12px; color: #aaa;">
                Generated by Personal AI Agent
            </div>
        </div>
      </body>
    </html>
    """
    msg.attach(MIMEText(html_body, 'html'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg, from_addr=EMAIL_SENDER, to_addrs=receivers)
        server.quit()
        print(f"✅ Email sent successfully!")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")


if __name__ == "__main__":
    print("🤖 Agent waking up...")
    news_html = get_summaries()
    if news_html:
        send_email(news_html)
    else:
        print("⚠️ No news found to send.")
    print("💤 Agent sleeping.")