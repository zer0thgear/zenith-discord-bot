import os

from dotenv import load_dotenv

load_dotenv()

class Settings:
    DISCORD_API_KEY = os.getenv("DISCORD_API_KEY")
    VENICE_API_KEY = os.getenv("VENICE_API_KEY")