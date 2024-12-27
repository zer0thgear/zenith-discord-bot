import json
import requests

import aiosqlite
import discord
import openai
from discord import app_commands

from settings import Settings

def convert_snowflake_to_timestamp(snowflake):
    return (int(snowflake) >> 22) + 1420070400000

async def fetch_conversations(guild_id, member_id, client):
    convocursor = await client.con.execute("SELECT convos FROM settings WHERE guild_id = ? AND member_id = ? LIMIT 1", (guild_id, member_id))
    convos = await convocursor.fetchone()
    await convocursor.close()
    if convos:
        convos = convos[0]
    else:
        convos = '["convo0"]'
    return json.loads(convos)

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
            
            if client.user.mentioned_in(message) or (message.reference is not None and message.reference.resolved.author == client.user):
                if message.content.startswith(f"<@{client.user.id}>"):
                    usermessage = message.content.split(f"<@{client.user.id}>", 1)[1].strip()
                else:
                    usermessage = message.content
                async with message.channel.typing():
                    modelcursor = await self.con.execute("SELECT text_model FROM settings WHERE guild_id = ? AND member_id = ? LIMIT 1", (message.guild.id, message.author.id))
                    model = await modelcursor.fetchone()
                    await modelcursor.close()
                    if model:
                        model = model[0]
                    convocursor = await self.con.execute("SELECT cur_convo FROM settings WHERE guild_id = ? AND member_id = ? LIMIT 1", (message.guild.id, message.author.id))
                    cur_convo = await convocursor.fetchone()
                    await convocursor.close()
                    if cur_convo:
                        cur_convo = cur_convo[0]
                    else:
                        cur_convo = "convo0"
                    historycursor = await self.con.execute("SELECT role, message FROM conversation_history WHERE guild_id = ? AND member_id = ? AND conversation_id = ? ORDER BY timestamp DESC", (message.guild.id, message.author.id, cur_convo))
                    rows = await historycursor.fetchall()
                    await historycursor.close()
                    rows.reverse()
                    await self.con.execute("INSERT INTO conversation_history (guild_id, member_id, timestamp, role, message, conversation_id) VALUES (?, ?, ?, ?, ?, ?)", (message.guild.id, message.author.id, convert_snowflake_to_timestamp(message.id), "user", usermessage, cur_convo))
                    messages = [{
                        "role": "system",
                        "content": f"{Settings.DEFAULT_SYSTEM_PROMPT}\nThe current user is {message.author.nick}."
                    }]
                    for (role, content) in rows:
                        messages.append({
                            "role": role,
                            "content": content
                        })
                    messages.append({
                        "role": "user",
                        "content": usermessage
                    })
                    chat_completion = await self.venice_client.chat.completions.create(
                        messages = messages,
                        model = model if model else Settings.DEFAULT_TEXT_MODEL
                    )
                    out_msg = await message.channel.send(chat_completion.choices[0].message.content)
                    await self.con.execute("INSERT INTO conversation_history (guild_id, member_id, timestamp, role, message, conversation_id) VALUES (?, ?, ?, ?, ?, ?)", (message.guild.id, message.author.id, convert_snowflake_to_timestamp(out_msg.id), "assistant", chat_completion.choices[0].message.content, cur_convo))
                    await self.con.commit()

    async def on_ready(self):
        print(f"Logged in as {client.user}!")

    async def setup_hook(self):
        await self.tree.sync(guild=discord.Object(id=Settings.SERVER_ID))
        print("Commands synced!")
        self.con = await aiosqlite.connect("settings_db.db")
        await self.con.execute("CREATE TABLE IF NOT EXISTS settings (guild_id, member_id, text_model, image_model, system_prompt, context_mode, cur_convo, convos, PRIMARY KEY (guild_id, member_id));")
        await self.con.execute("CREATE TABLE IF NOT EXISTS conversation_history (guild_id, member_id, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, role, message, conversation_id, PRIMARY KEY (guild_id, member_id, timestamp));")
        await self.con.commit()
        print("Database initialized!")

client = MyClient()

class ChooseTextModel(discord.ui.Select):
    def __init__(self):
        options=[discord.SelectOption(label=model[0]) for model in client.text_model_options]
        super().__init__(placeholder="Select a text model", options=options, row=0)
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

class ChooseConversation(discord.ui.Select):
    def __init__(self, convos):
        options = [discord.SelectOption(label=str(convo)) for convo in convos]
        super().__init__(placeholder="Select a conversation", options=options, row=0)
    async def callback(self, interaction: discord.Interaction):
        await client.con.execute("""
            INSERT INTO settings (guild_id, member_id, cur_convo) VALUES (?, ?, ?)
            ON CONFLICT (guild_id, member_id)
            DO UPDATE SET cur_convo = excluded.cur_convo;
        """, (interaction.guild.id, interaction.user.id, self.values[0]))
        await client.con.commit()
        await interaction.response.send_message(f"Selected conversation: {self.values[0]}", ephemeral=True)

class AddNewConversation(discord.ui.Button):
    def __init__(self, convos):
        super().__init__(style=discord.ButtonStyle.primary, label="Add new conversation")
        self.convos = convos
    async def callback(self, interaction: discord.Interaction):
        convo_num = len(self.convos)
        self.convos.append(f"convo{convo_num}")
        await client.con.execute("""
            INSERT INTO settings (guild_id, member_id, convos) VALUES (?, ?, ?)
            ON CONFLICT (guild_id, member_id)
            DO UPDATE SET convos = excluded.convos;
        """, (interaction.guild.id, interaction.user.id, json.dumps(self.convos)))
        await client.con.execute("""
            INSERT INTO settings (guild_id, member_id, cur_convo) VALUES (?, ?, ?)
            ON CONFLICT (guild_id, member_id)
            DO UPDATE SET cur_convo = excluded.cur_convo;
        """, (interaction.guild.id, interaction.user.id, f"convo{convo_num}"))
        await client.con.commit()
        await interaction.response.send_message(f"Added new conversation: convo{convo_num}, and set as current conversation", ephemeral=True)

class ChooseConversationView(discord.ui.View):
    def __init__(self, convos, *, timeout=180):
        super().__init__(timeout=timeout)
        self.add_item(ChooseConversation(convos))
        self.add_item(AddNewConversation(convos))
        
@client.tree.command(description="Select a text model", guild=discord.Object(id=Settings.SERVER_ID))
async def choose_text_model(interaction: discord.Interaction):
    await interaction.response.send_message("Select a text model", view=ChooseTextModelView(), ephemeral=True)

@client.tree.command(description="Select a conversation", guild=discord.Object(id=Settings.SERVER_ID))
async def choose_conversation(interaction: discord.Interaction):
    convos = await fetch_conversations(interaction.guild.id, interaction.user.id, client)
    await interaction.response.send_message("Select a conversation", view=ChooseConversationView(convos), ephemeral=True)

client.run(Settings.DISCORD_API_KEY)