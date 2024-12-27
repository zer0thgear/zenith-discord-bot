import json
import requests

import aiosqlite
import discord
import openai
from discord import app_commands

from components.conversation_manager import ChooseConversationView
from components.personality_manager import ChoosePersonalityView
from components.text_model_manager import ChooseTextModelView
from settings import Settings
from utils.venice_utils import fetch_text_models, get_chat_completion

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

class MyClient(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.text_model_options = fetch_text_models()

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
                    settingscursor = await self.con.execute("SELECT text_model, cur_convo, context_mode, personality FROM settings WHERE guild_id = ? AND member_id = ? LIMIT 1", (message.guild.id, message.author.id))
                    settingsrow = await settingscursor.fetchone()
                    if settingsrow:
                        model, cur_convo, mode, personality = settingsrow
                    else:
                        model = Settings.DEFAULT_TEXT_MODEL
                        cur_convo = "convo0"
                        mode = "focus"
                        personality = "None"
                    await settingscursor.close()
                    if not model:
                        model = Settings.DEFAULT_TEXT_MODEL
                    if not cur_convo:
                        cur_convo = "convo0"
                    if not mode:
                        mode = "focus"
                    if not personality:
                        personality = "None"
                    historycursor = await self.con.execute("SELECT timestamp, role, message FROM conversation_history WHERE guild_id = ? AND member_id = ? AND conversation_id = ? ORDER BY timestamp DESC LIMIT ?", (message.guild.id, message.author.id, cur_convo, Settings.DB_CONTEXT_LIMIT))
                    rows = await historycursor.fetchall()
                    await historycursor.close()
                    rows.reverse()
                    await self.con.execute("INSERT INTO conversation_history (guild_id, member_id, timestamp, role, message, conversation_id) VALUES (?, ?, ?, ?, ?, ?)", (message.guild.id, message.author.id, convert_snowflake_to_timestamp(message.id), "user", usermessage, cur_convo))
                    messages = [{
                        "role": "system",
                        "content": f"{Settings.DEFAULT_SYSTEM_PROMPT}\nThe current user is {message.author.nick}."
                    }]
                    if mode == "aware":
                        messages.append({
                            "role": "system",
                            "content": "For additional context, ambient messages from the current Discord channel have been included. Messages not from the current user will be prepended by (Ambient) [Username]: to indicate that a different user spoke these messages."
                        })
                        used_timestamps = set([timestamp for (timestamp, _, _) in rows])
                        ambient_msgs = [(convert_snowflake_to_timestamp(message.id), message.author.display_name, message.content) async for message in message.channel.history(limit=Settings.CHANNEL_CONTEXT_LIMIT, before=message)]
                        pruned_ambient_msgs = [(timestamp, author, content) for (timestamp, author, content) in ambient_msgs if timestamp not in used_timestamps]
                        if len(pruned_ambient_msgs) > 0:
                            rows = pruned_ambient_msgs + rows
                            rows = sorted(rows, key=lambda x: x[0])
                        for (_, author, content) in rows:
                            if author == message.author.nick or author == "user" or author == message.author.name:
                                messages.append({
                                    "role": "user",
                                    "content": content
                                })
                            elif author == client.user.display_name or author == "assistant":
                                messages.append({
                                    "role": "assistant",
                                    "content": content
                                })
                            else:
                                messages.append({
                                    "role": "system",
                                    "content": f"(Ambient) {author}: {content}"
                                })
                    else:
                        for (_, role, content) in rows:
                            messages.append({
                                "role": role,
                                "content": content
                            })
                    if personality != "None":
                        personalitycursor = await self.con.execute("SELECT personality_desc FROM personalities WHERE guild_id = ? AND member_id = ? AND personality_name = ? LIMIT 1", (message.guild.id, message.author.id, personality))
                        personality_desc = await personalitycursor.fetchone()
                        messages.append({
                            "role": "system",
                            "content": f"Current Personality Module: {personality_desc[0]}"
                        })
                    messages.append({
                        "role": "user",
                        "content": usermessage
                    })
                    chat_completion = await get_chat_completion(
                        messages = messages,
                        model = model if model else Settings.DEFAULT_TEXT_MODEL
                    )
                    out_msg = await message.channel.send(chat_completion)
                    await self.con.execute("INSERT INTO conversation_history (guild_id, member_id, timestamp, role, message, conversation_id) VALUES (?, ?, ?, ?, ?, ?)", (message.guild.id, message.author.id, convert_snowflake_to_timestamp(out_msg.id), "assistant", chat_completion, cur_convo))
                    await self.con.commit()

    async def on_ready(self):
        print(f"Logged in as {client.user}!")

    async def setup_hook(self):
        await self.tree.sync(guild=discord.Object(id=Settings.SERVER_ID))
        print("Commands synced!")
        self.con = await aiosqlite.connect("settings_db.db")
        await self.con.execute("CREATE TABLE IF NOT EXISTS settings (guild_id, member_id, text_model, image_model, system_prompt, context_mode, cur_convo, convos, personality, PRIMARY KEY (guild_id, member_id));")
        await self.con.execute("CREATE TABLE IF NOT EXISTS conversation_history (guild_id, member_id, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, role, message, conversation_id, PRIMARY KEY (guild_id, member_id, timestamp));")
        await self.con.execute("CREATE TABLE IF NOT EXISTS personalities (guild_id, member_id, personality_name, personality_desc, PRIMARY KEY (guild_id, member_id, personality_name));")
        await self.con.commit()
        print("Database initialized!")

client = MyClient()
        
@client.tree.command(description="Select a text model", guild=discord.Object(id=Settings.SERVER_ID))
async def choose_text_model(interaction: discord.Interaction):
    await interaction.response.send_message("Select a text model", view=ChooseTextModelView(client), ephemeral=True)

@client.tree.command(description="Select a conversation", guild=discord.Object(id=Settings.SERVER_ID))
async def choose_conversation(interaction: discord.Interaction):
    convos = await fetch_conversations(interaction.guild.id, interaction.user.id, client)
    await interaction.response.send_message("Select a conversation", view=ChooseConversationView(client, convos), ephemeral=True)

@client.tree.command(description="Toggle context mode", guild=discord.Object(id=Settings.SERVER_ID))
async def toggle_context_mode(interaction: discord.Interaction):
    modecursor = await client.con.execute("SELECT context_mode FROM settings WHERE guild_id = ? AND member_id = ? LIMIT 1", (interaction.guild.id, interaction.user.id))
    mode = await modecursor.fetchone()
    await modecursor.close()
    if mode[0] == "focus":
        mode = "aware"
    else:
        mode = "focus"
    await client.con.execute("""
        INSERT INTO settings (guild_id, member_id, context_mode) VALUES (?, ?, ?)
        ON CONFLICT (guild_id, member_id)
        DO UPDATE SET context_mode = excluded.context_mode;
    """, (interaction.guild.id, interaction.user.id, mode))
    await client.con.commit()
    await interaction.response.send_message(f"Context mode toggled to {mode}", ephemeral=True)

@client.tree.command(description="Select a personality module", guild=discord.Object(id=Settings.SERVER_ID))
async def choose_personality(interaction: discord.Interaction):
    personalitiescursor = await client.con.execute("SELECT personality_name FROM personalities WHERE guild_id = ? AND member_id = ?", (interaction.guild.id, interaction.user.id))
    personalities = await personalitiescursor.fetchall()
    await personalitiescursor.close()
    if len(personalities) == 0:
        personalities = ["None"]
        await client.con.execute("""
            INSERT INTO personalities (guild_id, member_id, personality_name, personality_desc) VALUES (?, ?, ?, ?)""",
            (interaction.guild.id, interaction.user.id, "None", "Default personality module"))
    else:
        personalities = [personality[0] for personality in personalities]
    await interaction.response.send_message("Select a personality module", view=ChoosePersonalityView(client, personalities), ephemeral=True)

client.run(Settings.DISCORD_API_KEY)