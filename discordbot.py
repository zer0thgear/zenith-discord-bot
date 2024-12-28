import discord
from discord import app_commands

from components.conversation_manager import ChooseConversationView
from components.personality_manager import ChoosePersonalityView
from components.text_model_manager import ChooseTextModelView
from settings import Settings
from utils.db_utils import DBEngine
from utils.venice_utils import fetch_text_models, get_chat_completion

def convert_snowflake_to_timestamp(snowflake):
    return (int(snowflake) >> 22) + 1420070400000

class MyClient(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.text_model_options = fetch_text_models()

    async def close(self):
        await self.DB_Engine.close()
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
                    model, cur_convo, mode, personality = await self.DB_Engine.get_settings(message.guild.id, message.author.id)
                    rows = await self.DB_Engine.get_history(message.guild.id, message.author.id, cur_convo)
                    await self.DB_Engine.add_message(message.guild.id, message.author.id, convert_snowflake_to_timestamp(message.id), "user", usermessage, cur_convo)
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
                        personality_desc = await self.DB_Engine.get_personality_desc(message.guild.id, message.author.id, personality)
                        messages.append({
                            "role": "system",
                            "content": f"Current Personality Module: {personality_desc}"
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
                    await self.DB_Engine.add_message(message.guild.id, message.author.id, convert_snowflake_to_timestamp(out_msg.id), "assistant", chat_completion, cur_convo)

    async def on_ready(self):
        print(f"Logged in as {client.user}!")

    async def setup_hook(self):
        await self.tree.sync(guild=discord.Object(id=Settings.SERVER_ID))
        print("Commands synced!")
        self.DB_Engine = await DBEngine.init_engine(Settings.DB_PATH)

client = MyClient()
        
@client.tree.command(description="Select a text model", guild=discord.Object(id=Settings.SERVER_ID))
async def choose_text_model(interaction: discord.Interaction):
    await interaction.response.send_message("Select a text model", view=ChooseTextModelView(client), ephemeral=True)

@client.tree.command(description="Select a conversation", guild=discord.Object(id=Settings.SERVER_ID))
async def choose_conversation(interaction: discord.Interaction):
    convos = await client.DB_Engine.get_conversations(interaction.guild.id, interaction.user.id)
    await interaction.response.send_message("Select a conversation", view=ChooseConversationView(client, convos), ephemeral=True)

@client.tree.command(description="Toggle context mode", guild=discord.Object(id=Settings.SERVER_ID))
async def toggle_context_mode(interaction: discord.Interaction):
    mode = await client.DB_Engine.get_single_setting(interaction.guild.id, interaction.user.id, "context_mode")
    if mode == "focus":
        mode = "aware"
    else:
        mode = "focus"
    await client.DB_Engine.set_setting(interaction.guild.id, interaction.user.id, "context_mode", mode)
    await interaction.response.send_message(f"Context mode toggled to {mode}", ephemeral=True)

@client.tree.command(description="Select a personality module", guild=discord.Object(id=Settings.SERVER_ID))
async def choose_personality(interaction: discord.Interaction):
    personalities = await client.DB_Engine.get_personalities(interaction.guild.id, interaction.user.id)
    if len(personalities) == 0:
        personalities = ["None"]
        await client.DB_Engine.add_personality(interaction.guild.id, interaction.user.id, "None", "Default personality module")
    else:
        personalities = [personality[0] for personality in personalities]
    await interaction.response.send_message("Select a personality module", view=ChoosePersonalityView(client, personalities), ephemeral=True)

client.run(Settings.DISCORD_API_KEY)