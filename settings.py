import os

from dotenv import load_dotenv

load_dotenv()

class Settings:
    BOT_ID = os.getenv("BOT_ID")
    DISCORD_API_KEY = os.getenv("DISCORD_API_KEY")
    SERVER_ID = os.getenv("SERVER_ID")
    VENICE_API_KEY = os.getenv("VENICE_API_KEY")