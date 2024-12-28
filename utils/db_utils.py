import json

import aiosqlite

from settings import Settings

class DBEngine():
    @classmethod
    async def init_engine(cls, db_path):
        self = cls()
        self.con = await aiosqlite.connect(db_path)
        await self.con.execute("CREATE TABLE IF NOT EXISTS settings (guild_id, member_id, text_model, image_model, system_prompt, context_mode, cur_convo, convos, personality, PRIMARY KEY (guild_id, member_id));")
        await self.con.execute("CREATE TABLE IF NOT EXISTS conversation_history (guild_id, member_id, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, role, message, conversation_id, PRIMARY KEY (guild_id, member_id, timestamp));")
        await self.con.execute("CREATE TABLE IF NOT EXISTS personalities (guild_id, member_id, personality_name, personality_desc, PRIMARY KEY (guild_id, member_id, personality_name));")
        await self.con.commit()
        print("Database initialized!")
        return self
    
    async def add_message(self, guild_id, member_id, timestamp, role, message, convo_id):
        await self.con.execute("INSERT INTO conversation_history (guild_id, member_id, timestamp, role, message, conversation_id) VALUES (?, ?, ?, ?, ?, ?)", (guild_id, member_id, timestamp, role, message, convo_id))
        await self.con.commit()

    async def add_personality(self, guild_id, member_id, personality_name, personality_desc):
        await self.con.execute("INSERT INTO personalities (guild_id, member_id, personality_name, personality_desc) VALUES (?, ?, ?, ?)", (guild_id, member_id, personality_name, personality_desc))
        await self.con.commit()

    async def close(self):
        await self.con.close()

    async def get_conversations(self, guild_id, member_id):
        convoscursor = await self.con.execute("SELECT convos FROM settings WHERE guild_id = ? AND member_id = ? LIMIT 1", (guild_id, member_id))
        convos = await convoscursor.fetchone()
        await convoscursor.close()
        if convos:
            convos = convos[0]
        else:
            convos = '["convo0"]'
        return json.loads(convos)

    async def get_history(self, guild_id, member_id, convo_id):
        historycursor = await self.con.execute("SELECT timestamp, role, message FROM conversation_history WHERE guild_id = ? AND member_id = ? AND conversation_id = ? ORDER BY timestamp DESC LIMIT ?", (guild_id, member_id, convo_id, Settings.DB_CONTEXT_LIMIT))
        history = await historycursor.fetchall()
        await historycursor.close()
        history.reverse()
        return history

    async def get_personalities(self, guild_id, member_id):
        personalitiescursor = await self.con.execute("SELECT personality_name FROM personalities WHERE guild_id = ? AND member_id = ?", (guild_id, member_id))
        personalities = await personalitiescursor.fetchall()
        await personalitiescursor.close()
        return personalities

    async def get_personality_desc(self, guild_id, member_id, personality_name):
        personalitycursor = await self.con.execute("SELECT personality_desc FROM personalities WHERE guild_id = ? AND member_id = ? AND personality_name = ? LIMIT 1", (guild_id, member_id, personality_name))
        personality_desc = await personalitycursor.fetchone()
        await personalitycursor.close()
        return personality_desc[0]

    async def get_settings(self, guild_id, member_id):
        """
        Returns settings in the order: model, cur_convo, mode, personality
        """
        settingscursor = await self.con.execute("SELECT text_model, cur_convo, context_mode, personality FROM settings WHERE guild_id = ? AND member_id = ? LIMIT 1", (guild_id, member_id))
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
        return model, cur_convo, mode, personality
    
    async def get_single_setting(self, guild_id, member_id, setting):
        settingscursor = await self.con.execute(f"SELECT {setting} FROM settings WHERE guild_id = ? AND member_id = ? LIMIT 1", (guild_id, member_id))
        setting = await settingscursor.fetchone()
        await settingscursor.close()
        return setting[0]
    
    async def set_setting(self, guild_id, member_id, setting, value):
        await self.con.execute(f"""
            INSERT INTO settings (guild_id, member_id, {setting}) VALUES (?, ?, ?)
            ON CONFLICT (guild_id, member_id)
            DO UPDATE SET {setting} = excluded.{setting};
        """, (guild_id, member_id, value))
        await self.con.commit()