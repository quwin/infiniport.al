import aiosqlite
from constants import SKILLS

async def init_db():
    async with aiosqlite.connect('leaderboard.db') as conn:
        c = await conn.cursor()
        await c.execute(
            '''CREATE TABLE IF NOT EXISTS total
            (user_id text PRIMARY KEY, username text, level integer, exp float)'''
        )
        await c.execute(
            '''CREATE TABLE IF NOT EXISTS guilds
            (id text PRIMARY KEY, handle text, emblem text,
            shard_price integer, land_count integer)'''
        )
        for skill in SKILLS:
            await c.execute(
                f'''CREATE TABLE IF NOT EXISTS {skill}
                (user_id text PRIMARY KEY, username text,
                level integer, exp float, current_exp float)'''
            )


        await conn.commit()
    # create job database
    async with aiosqlite.connect('jobs.db') as jobs:
        await jobs.execute('''
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                author_id INTEGER,
                item TEXT,
                quantity INTEGER,
                reward TEXT,
                details TEXT,
                time_limit REAL,
                claimer_id INTEGER,
                message_id INTEGER,
                channel_id INTEGER,
                server_id INTEGER
            )
        ''')
        await jobs.commit()
    # create discord stats database
    async with aiosqlite.connect('discord.db') as discord:
        await discord.execute(
        '''CREATE TABLE IF NOT EXISTS discord_servers
        (server_id text PRIMARY KEY,
        premium REAL,
        linked_guild text,
        global_tasks boolean,
        account_linking boolean,
        admin_role text,
        role_ids text,
        role_requirements text,
        role_numbers text
        )'''
        )
        await discord.execute(
            '''CREATE TABLE IF NOT EXISTS discord_users
            (user_id text PRIMARY KEY,
            wallets text,
            pixels_ids text,
            primary_id text,
            access_token text,
            refresh_token text
            )'''
        )
        await discord.commit()
        
    print('Databases Initialized!')


async def update_skills(c, json, total_level, total_exp):
    if json is None:
        return
    await c.execute(
      '''INSERT OR REPLACE INTO total (user_id, username, level, exp)
      VALUES (?, ?, ?, ?)''',
      (json['_id'], json['username'], total_level, total_exp))
    for skill in SKILLS:
      skill_data = json['levels'].get(skill, None)
      if skill_data:
          await c.execute(
              f'''INSERT OR REPLACE INTO {skill}
              (user_id, username , level, exp, current_exp) VALUES (?, ?, ?, ?, ?)''',
              (json['_id'], json['username'], skill_data['level'],
               skill_data['totalExp'], skill_data['exp']))
    
    # print(f'User ID {json["_id"]} updated!')

async def init_guild_db(guild_data, server_id = None):
    async with aiosqlite.connect('discord.db') as discord, aiosqlite.connect('leaderboard.db') as leaderboard: 
        lb = await leaderboard.cursor()
        id = guild_data['_id']
        await lb.execute(
            '''INSERT OR REPLACE INTO guilds
            (id, handle, emblem, shard_price, land_count)
            VALUES (?, ?, ?, ?, ?)''',
            (id, guild_data['handle'], guild_data.get('emblem', ''), guild_data['membershipsCount'], guild_data['mapCount'],)
        )
        await lb.execute(
            f'''CREATE TABLE IF NOT EXISTS guild_{id}
            (user_id text PRIMARY KEY, username text, role text)'''
        )
        
        if server_id:
            async with discord.execute('SELECT 1 FROM discord_servers WHERE server_id = ?', (server_id,)) as cursor:
                exists = await cursor.fetchone()
                if exists:
                    await discord.execute('UPDATE discord_servers SET linked_guild = ? WHERE server_id = ?', (id, server_id))
                else:
                    await discord.execute('''
                        INSERT INTO discord_servers (server_id, linked_guild)
                        VALUES (?, ?)
                    ''', (server_id, id))
                    
            await discord.commit()
        
        await leaderboard.commit()

async def update_job_claimer(job_id, claimer_id):
    async with aiosqlite.connect('jobs.db') as db:
        await db.execute('''
            UPDATE jobs
            SET claimer_id = ?
            WHERE job_id = ?
        ''', (claimer_id, job_id))
        await db.commit()

async def update_job_message(job_id, message_id):
    async with aiosqlite.connect('jobs.db') as db:
        await db.execute('''
            UPDATE jobs
            SET message_id = ?
            WHERE job_id = ?
        ''', (message_id, job_id))
        await db.commit()

async def delete_job(job_id):
    try:
        async with aiosqlite.connect('jobs.db') as db:
            await db.execute('''
                DELETE FROM jobs
                WHERE job_id = ?
            ''', (job_id,))
            await db.commit()
    except Exception as e:
        print(f"An task deletion error occurred: {e}")

async def fetch_job(job_id):
    async with aiosqlite.connect('jobs.db') as db, db.execute('SELECT * FROM jobs WHERE job_id = ?', (job_id,)) as cursor:
        job = await cursor.fetchone()
        return job

async def fetch_job_location(job_id):
    async with aiosqlite.connect('jobs.db') as db, db.execute('SELECT message_id, channel_id, server_id FROM jobs WHERE job_id = ?', (job_id,)) as cursor:
        job = await cursor.fetchone()
        return job

async def add_job(job_id, author_id, item, quantity, reward, details, time_limit, message_id, channel_id, server_id, claimer_id=None):
    async with aiosqlite.connect('jobs.db') as db:
        await db.execute('''
            INSERT OR REPLACE INTO jobs (job_id, author_id, item, quantity, reward, details, time_limit, claimer_id, message_id, channel_id, server_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (job_id, author_id, item, quantity, reward, details, time_limit, claimer_id, message_id, channel_id, server_id))
        await db.commit()

async def fetch_unclaimed_jobs(page_number: int = 1, server: str | None = None):
    if server:
        limit = 4
        offset = 4 * (page_number - 1)
        query = 'SELECT * FROM jobs WHERE claimer_id IS NULL AND server_id = ? LIMIT ? OFFSET ?'
        async with aiosqlite.connect('jobs.db') as db, db.execute(query, (server, limit, offset)) as cursor:
            return await cursor.fetchall()
    else:
        async with aiosqlite.connect('jobs.db') as db, db.execute(
            f'SELECT * FROM jobs WHERE claimer_id IS NULL LIMIT 4 OFFSET {4 * (page_number - 1)}') as cursor:
            return await cursor.fetchall()

async def fetch_linked_wallets(user_id):
    async with aiosqlite.connect('discord.db') as db, db.execute('SELECT * FROM discord_users WHERE user_id = ?', (user_id,)) as cursor:
        return await cursor.fetchone()

async def add_collab_tokens(user_id, access_token, refresh_token):
    async with aiosqlite.connect('discord.db') as db:
        await db.execute(
        '''INSERT OR REPLACE INTO discord_users (user_id, access_token, refresh_token)
        VALUES (?, ?, ?)''',
        (user_id, access_token, refresh_token)
        )
        await db.commit()

async def add_collab_wallets(user_id, wallets, pixels_ids):
    async with aiosqlite.connect('discord.db') as db:
        await db.execute(
        '''INSERT OR REPLACE INTO discord_users (user_id, wallets, pixels_ids)
        VALUES (?, ?, ?)''',
        (user_id, wallets, pixels_ids)
        )
        await db.commit()
        print(f"Inserted {wallets} linked to {pixels_ids} into database for {user_id}!")

async def batch_update_players(cursor, total_data_batch, skill_data_batch):
    if 'total' in skill_data_batch:
        del skill_data_batch['total']
    await cursor.executemany(
        '''INSERT OR REPLACE INTO total (user_id, username, level, exp)
      VALUES (?, ?, ?, ?)''', total_data_batch)
    total_data_batch.clear()
    
    for skill, batch in skill_data_batch.items():
        await cursor.executemany(
            f'''INSERT OR REPLACE INTO {skill}
          (user_id, username, level, exp, current_exp)
          VALUES (?, ?, ?, ?, ?)''', batch)
        batch.clear()

async def get_discord_roles(server_id):
    async with aiosqlite.connect('discord.db') as db, db.execute('SELECT * FROM discord_servers WHERE server_id = ?', (server_id,)) as cursor:
        result = await cursor.fetchone()
        return result

async def get_guild_handle(guild_id):
    async with aiosqlite.connect('leaderboard.db') as db2, db2.execute('SELECT handle FROM guilds WHERE id = ?', (guild_id,)) as cursor2:
        guild_handle = await cursor2.fetchone()
        return guild_handle
                