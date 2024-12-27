import discord

class ChooseTextModel(discord.ui.Select):
    def __init__(self, client):
        self.client = client
        options=[discord.SelectOption(label=model[0]) for model in client.text_model_options]
        super().__init__(placeholder="Select a text model", options=options, row=0)
    async def callback(self, interaction: discord.Interaction):
        await self.client.con.execute("""
            INSERT INTO settings (guild_id, member_id, text_model) VALUES (?, ?, ?)
            ON CONFLICT (guild_id, member_id)
            DO UPDATE SET text_model = excluded.text_model;
        """, (interaction.guild.id, interaction.user.id, self.values[0]))
        await self.client.con.commit()
        await interaction.response.send_message(f"Selected model: {self.values[0]}", ephemeral=True)

class ChooseTextModelView(discord.ui.View):
    def __init__(self, client, *, timeout=180):
        super().__init__(timeout=timeout)
        self.add_item(ChooseTextModel(client))