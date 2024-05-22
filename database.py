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
                claimer_id INTEGER
            )
        ''')
        await jobs.commit()

#    async with aiosqlite.connect('discord.db') as discord:
#        await discord.execute(
#        '''CREATE TABLE IF NOT EXISTS discord_servers
#        (server_id text PRIMARY KEY,
#        premium REAL, linked_guild text)'''
#        )
#        await discord.execute(
#            '''CREATE TABLE IF NOT EXISTS discord_users
#            (user_id text PRIMARY KEY,
#            wallets text, pixels_accounts text, access_token text, refresh_token text)'''
#        )
#        await discord.commit()
        
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
    
    print(f'User ID {json["_id"]} updated!')


async def database_remove(user_id):
  async with aiosqlite.connect('leaderboard.db') as conn:
      c = await conn.cursor()
      await c.execute("DELETE FROM total WHERE user_id = ?", (user_id,))
      try:
          for skill in SKILLS:
              await c.execute(f"DELETE FROM {skill} WHERE user_id = ?", (user_id,))
      except aiosqlite.Error as e:
          print(f"An error occurred: {e}")
      finally:
          await conn.commit()
          print(f"purged {user_id} from database")

async def init_guild_db(server_id, guild_id, conn):
    c = await conn.cursor()
    await c.execute(
        f'''CREATE TABLE IF NOT EXISTS guild_{guild_id}
        (user_id text PRIMARY KEY, username text, role text)'''
    )
    await c.execute(
        '''INSERT OR REPLACE INTO discord_servers (server_id, linked_guild)
        VALUES (?, ?)''',
        (server_id, guild_id)
    )

async def update_job_claimer(job_id, claimer_id):
    async with aiosqlite.connect('jobs.db') as db:
        await db.execute('''
            UPDATE jobs
            SET claimer_id = ?
            WHERE job_id = ?
        ''', (claimer_id, job_id))
        await db.commit()

async def delete_job(job_id):
    async with aiosqlite.connect('jobs.db') as db:
        await db.execute('''
            DELETE FROM jobs
            WHERE job_id = ?
        ''', (job_id,))
        await db.commit()

async def fetch_job(job_id):
    async with aiosqlite.connect('jobs.db') as db, db.execute('SELECT * FROM jobs WHERE job_id = ?', (job_id,)) as cursor:
        job = await cursor.fetchone()
        return job

async def add_job(job_id, author_id, item, quantity, reward, details, time_limit, claimer_id=None):
    async with aiosqlite.connect('jobs.db') as db:
        await db.execute('''
            INSERT OR REPLACE INTO jobs (job_id, author_id, item, quantity, reward, details, time_limit, claimer_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (job_id, author_id, item, quantity, reward, details, time_limit, claimer_id))
        await db.commit()

async def fetch_unclaimed_jobs():
    async with aiosqlite.connect('jobs.db') as db, db.execute('SELECT * FROM jobs WHERE claimer_id IS NULL') as cursor:
        return await cursor.fetchall()

async def fetch_linked_wallets(discord_id):
    async with aiosqlite.connect('leaderboard.db') as db, db.execute('SELECT * FROM total WHERE linked_discord = ?', (discord_id,)) as cursor:
        return await cursor.fetchall()