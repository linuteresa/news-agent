
import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))

load_dotenv(dotenv_path=os.path.join(basedir, "cred.env"))

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
NUM_ARTICLES = int(os.getenv("NUM_ARTICLES", 3))

def get_email_receivers():
    receivers = []
    for key, value in os.environ.items():
        if key.startswith("EMAIL_RECEIVER"):
            receivers.append(value)
    return receivers
