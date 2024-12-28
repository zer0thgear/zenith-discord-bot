import traceback

import discord

class ChoosePersonality(discord.ui.Select):
    def __init__(self, client, personalities):
        self.client = client
        options = [discord.SelectOption(label=personality) for personality in personalities]
        super().__init__(placeholder="Select a personality module", options=options, row=0)
    async def callback(self, interaction: discord.Interaction):
        await self.client.DB_Engine.set_setting(interaction.guild.id, interaction.user.id, "personality", self.values[0])
        await interaction.response.send_message(f"Selected personality module: {self.values[0]}", ephemeral=True)

class AddNewPersonalityModal(discord.ui.Modal, title='New Personality'):
    def __init__(self, client):
        self.client = client
        super().__init__()

    name = discord.ui.TextInput(label='Personality Name', placeholder='Enter a name for the personality module')
    desc = discord.ui.TextInput(label='Personality Description', placeholder='Enter a description for the personality module', style=discord.TextStyle.long)

    async def on_submit(self, interaction: discord.Interaction):
        await self.client.DB_Engine.add_personality(interaction.guild.id, interaction.user.id, self.name.value, self.desc.value)
        await interaction.response.send_message(f"Added new personality module: {self.name.value}", ephemeral=True)
    
    async def on_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"An error occurred: {error}", ephemeral=True)
        traceback.print_exception(type(error), error, error.__traceback__)

class AddNewPersonalityButton(discord.ui.Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.primary, label="Add new personality module")

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(AddNewPersonalityModal())

class ChoosePersonalityView(discord.ui.View):
    def __init__(self, client, personalities, *, timeout=180):
        super().__init__(timeout=timeout)
        self.add_item(ChoosePersonality(client, personalities))
        self.add_item(AddNewPersonalityButton())