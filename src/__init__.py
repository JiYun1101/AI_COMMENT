from pathlib import Path

from dotenv import load_dotenv


# Local execution uses the repository-level .env.local file documented in README.
# Existing shell/CI environment variables keep priority because override=False.
load_dotenv(Path(__file__).resolve().parent.parent / ".env.local", override=False)
