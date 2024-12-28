import json

import discord

class ChooseConversation(discord.ui.Select):
    def __init__(self, client, convos):
        self.client = client
        options = [discord.SelectOption(label=str(convo)) for convo in convos]
        super().__init__(placeholder="Select a conversation", options=options, row=0)
    async def callback(self, interaction: discord.Interaction):
        await self.client.DB_Engine.set_setting(interaction.guild.id, interaction.user.id, "cur_convo", self.values[0])
        await interaction.response.send_message(f"Selected conversation: {self.values[0]}", ephemeral=True)

class AddNewConversation(discord.ui.Button):
    def __init__(self, client, convos):
        self.client = client
        super().__init__(style=discord.ButtonStyle.primary, label="Add new conversation")
        self.convos = convos
    async def callback(self, interaction: discord.Interaction):
        convo_num = len(self.convos)
        while convo_num in self.convos:
            convo_num += 1
        self.convos.append(f"convo{convo_num}")
        await self.client.DB_Engine.set_setting(interaction.guild.id, interaction.user.id, "convos", json.dumps(self.convos))
        await self.client.DB_Engine.set_setting(interaction.guild.id, interaction.user.id, "cur_convo", f"convo{convo_num}")
        await interaction.response.send_message(f"Added new conversation: convo{convo_num}, and set as current conversation", ephemeral=True)

class ChooseConversationView(discord.ui.View):
    def __init__(self, client, convos, *, timeout=180):
        super().__init__(timeout=timeout)
        self.add_item(ChooseConversation(client, convos))
        self.add_item(AddNewConversation(client, convos))