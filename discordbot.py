import json
import requests

import aiosqlite
import discord
import openai
from discord import app_commands

from settings import Settings

def fetch_text_models():
    venice_url = f"{Settings.VENICE_BASE_URL}/models"
    headers = {"Authorization": f"Bearer {Settings.VENICE_API_KEY}"}
    response = requests.request("GET", venice_url, headers=headers)
    return [(model["id"], model["model_spec"]["availableContextTokens"]) for model in json.loads(response.text)["data"] if model["type"] == "text"]

class MyClient(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.text_model_options = fetch_text_models()
        self.venice_client = openai.AsyncOpenAI(base_url=Settings.VENICE_BASE_URL, api_key=Settings.VENICE_API_KEY)

    async def close(self):
        await self.con.close()
        await super().close()

    async def on_message(self, message):
            if message.author == client.user:
                return
            
            if client.user.mentioned_in(message):
                async with message.channel.typing():
                    chat_completion = await self.venice_client.chat.completions.create(
                        messages=[{
                            "role": "system",
                            "content": f"{Settings.DEFAULT_SYSTEM_PROMPT}\nThe current user is {message.author.nick}."
                        }, {
                            "role": "user",
                            "content": message.content
                        }],
                        model=Settings.DEFAULT_TEXT_MODEL
                    )
                    await message.channel.send(chat_completion.choices[0].message.content)

    async def on_ready(self):
        print(f"Logged in as {client.user}!")

    async def setup_hook(self):
        await self.tree.sync(guild=discord.Object(id=Settings.SERVER_ID))
        print("Commands synced!")
        self.con = await aiosqlite.connect("settings_db.db")
        await self.con.execute("CREATE TABLE IF NOT EXISTS settings (guild_id, member_id, text_model, image_model, system_prompt, PRIMARY KEY (guild_id, member_id));")
        await self.con.commit()
        print("Database initialized!")

client = MyClient()

class ChooseTextModel(discord.ui.Select):
    def __init__(self):
        options=[discord.SelectOption(label=model[0]) for model in client.text_model_options]
        super().__init__(placeholder="Select a text model", options=options)
    async def callback(self, interaction: discord.Interaction):
        await client.con.execute("""
            INSERT INTO settings (guild_id, member_id, text_model) VALUES (?, ?, ?)
            ON CONFLICT (guild_id, member_id)
            DO UPDATE SET text_model = excluded.text_model;
        """, (interaction.guild.id, interaction.user.id, self.values[0]))
        await client.con.commit()
        await interaction.response.send_message(f"Selected model: {self.values[0]}", ephemeral=True)

class ChooseTextModelView(discord.ui.View):
    def __init__(self, *, timeout=180):
        super().__init__(timeout=timeout)
        self.add_item(ChooseTextModel())

@client.tree.command(description="Select a text model", guild=discord.Object(id=Settings.SERVER_ID))
async def choose_text_model(interaction: discord.Interaction):
    await interaction.response.send_message("Select a text model", view=ChooseTextModelView(), ephemeral=True)

client.run(Settings.DISCORD_API_KEY)