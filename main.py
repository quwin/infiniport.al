import discord
from discord.ext import commands, tasks
from discord import app_commands
from profile_utils import lookup_profile, embed_profile
from database import init_db, init_guild_db
from leaderboard import manage_leaderboard
from constants import TOKEN, SkillEnum, SortEnum
from guild import guild_data, guild_update
from land import speck_data, nft_land_data
from modal import JobInput
from job import JobView, show_unclaimed_jobs
from collab_land import collab_channel, CollabButtons
import aiosqlite
import aiohttp

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
client = discord.Client(intents=intents, command_prefix='!')
tree = app_commands.CommandTree(client)


@client.event
async def on_ready():
  await tree.sync(guild=discord.Object(id=1234015429874417706))
  print(f'We have logged in as {client.application_id}')
  await init_db()
  await init_job_views(client)
  client.add_view(CollabButtons())
  await collab_channel(client)
  batch_speck_update.start()
  batch_nft_land_update.start()
  # update_voice_channel_name.start()
  # batch_guild_update.start()

async def init_job_views(client: discord.Client):
  async with aiosqlite.connect('jobs.db') as db, db.execute('SELECT job_id FROM jobs') as cursor:
    jobs = await cursor.fetchall()

  for job_id in jobs:
    client.add_view(JobView(job_id[0]))

@tree.command(name="clear_commands", description="",
              guild=discord.Object(id=1234015429874417706))
async def clear_commands(interaction, server: str | None = None):
  if interaction.user.id != 239235420104163328:
    return
  tree.clear_commands(guild=None)
  if server is None:
    await tree.sync()
  else:
    await tree.sync(guild=discord.Object(id=server))
  await interaction.response.send_message('Command tree removed!', ephemeral=True)

@tree.command(name="add_commands", description="",
             guild=discord.Object(id=1234015429874417706))
async def add_commands(interaction, server: str | None = None):
  if interaction.user.id != 239235420104163328:
    return
  if server is None:
    await tree.sync()
  else:
    await tree.sync(guild=discord.Object(id=int(server)))
  await interaction.response.send_message('Command tree synced!', ephemeral=True)

async def link_profile(interaction):
  user_id = interaction.user.id
  
  
@tree.command(name="lookup",
              description="Lookup a player's Pixels profile")
async def lookup(interaction, input: str):
  async with aiosqlite.connect('leaderboard.db') as conn:
    c = await conn.cursor()
    result = await lookup_profile(c, input)
    if result is None:
      string = f"Could not find the player `{input}`. Please try again"
      await interaction.response.send_message(string, ephemeral=True)
      return
    (data, total_levels, total_skills) = result

    embed = embed_profile(data, total_levels, total_skills)
    await interaction.response.send_message(embed=embed)

    await conn.commit()

  pass

@tree.command(name="global_leaderboard",
              description="Look at a ranking of (almost) every Pixels Player!")
@app_commands.describe(skill="Select the skill to display",
                       sort="Select the sorting method",
                       page_number="Page number of the leaderboard")
async def global_leaderboard(interaction: discord.Interaction,
                             skill: SkillEnum = SkillEnum.NONE,
                             sort: SortEnum = SortEnum.LEVEL,
                             page_number: int = 1):
  skill_value = skill.value
  sort_value = sort.value
  await manage_leaderboard(interaction, skill_value, sort_value, page_number)


@tree.command(name="leaderboard",
              description="Look at your server's Leaderboard!")
@app_commands.describe(skill="Select the skill to display",
                       sort="Select the sorting method",
                       page_number="Page number of the leaderboard")
async def leaderboard(interaction: discord.Interaction,
                             skill: SkillEnum = SkillEnum.NONE,
                             sort: SortEnum = SortEnum.LEVEL,
                             page_number: int = 1):
  skill_value = skill.value
  sort_value = sort.value
  server_id = interaction.guild.id
  await manage_leaderboard(interaction, skill_value, sort_value, page_number, server_id)


async def assignguild(interaction, guild_name: str):
  async with aiosqlite.connect(
      'leaderboard.db') as conn, aiohttp.ClientSession() as session:
    data = await guild_data(session, guild_name)
    guild_info = data.get('guild', None)
    if guild_info is None:
      await interaction.response.send_message(content=f"I could not find a guild with the handle @{guild_name}!", ephemeral=True)
      return
    guild_id = guild_info.get('id', None)
    if guild_id is None:
      return
    await init_guild_db(interaction.guild.id, guild_id, conn)
    await guild_update(conn, data)
    await conn.commit()

# Define the group
job_group = app_commands.Group(name="task", description="View, modify, and create tasks for other users to complete!")

# Create the subjobs
@job_group.command(name="create", description="Create a claimable task!")
async def create(interaction: discord.Interaction):
  await interaction.response.send_modal(JobInput(client))

tree.add_command(job_group)

# Main /taskboard
@tree.command(name="taskboard",
  description="View the tasks available to complete!")
async def taskboard(interaction: discord.Interaction):
  embed = await show_unclaimed_jobs(interaction)
  await interaction.response.send_message(embed=embed, ephemeral=True)


@tasks.loop(minutes=2880)
async def batch_speck_update():
  async with aiosqlite.connect(
      'leaderboard.db') as conn, aiohttp.ClientSession() as session:
    await speck_data(conn, session)


@tasks.loop(minutes=120)
async def batch_nft_land_update():
  async with aiosqlite.connect(
      'leaderboard.db') as conn, aiohttp.ClientSession() as session:
    await nft_land_data(conn, session)

@tasks.loop(minutes=60)
async def update_voice_channel_name():
  guild_id = 880961748092477453
  return

client.run(TOKEN)
