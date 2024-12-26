import discord
#from discord import ui

from settings import Settings

class MyClient(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)

    async def on_ready(self):
        print(f"Logged in as {client.user}!")

    async def on_message(message):
        if message.author == client.user:
            return
        
        if client.user.mentioned_in(message):
            await message.channel.send("Hello!")

client = MyClient()

client.run(Settings.DISCORD_API_KEY)