from constants import ICON, ICON_END, SKILLS
import discord
import asyncio
import aiosqlite


class LeaderboardView(discord.ui.View):

    def __init__(self,
                 interaction,
                 table_name='total',
                 arg='level',
                 page_number=1,
                 server_id=None):
        super().__init__(timeout=60.0)

        self.interaction = interaction
        self.table_name = table_name
        self.arg = arg
        self.page_number = page_number
        self.server_id = server_id

    @discord.ui.button(label='Previous', style=discord.ButtonStyle.grey)
    async def previous_button(self, interaction: discord.Interaction,
                              _button: discord.ui.Button):
        self.page_number = max(1, self.page_number - 1)
        await self.update_leaderboard(interaction)

    @discord.ui.button(label='Flip Order', style=discord.ButtonStyle.blurple)
    async def flip_button(self, interaction: discord.Interaction,
                          _button: discord.ui.Button):
        self.arg = 'exp' if self.arg == 'level' else 'level'
        await self.update_leaderboard(interaction)

    @discord.ui.button(label='Next', style=discord.ButtonStyle.grey)
    async def next_button(self, interaction: discord.Interaction,
                          _button: discord.ui.Button):
        self.page_number += 1
        await self.update_leaderboard(interaction)

    async def update_leaderboard(self, interaction: discord.Interaction):
        embed = await leaderboard_func(self.table_name, self.arg,
                                       self.page_number, self.server_id)
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        try:
            await self.interaction.edit_original_response(view=None)
        except Exception as e:
            print(f"Failed to edit message on timeout: {e}")

async def manage_leaderboard(interaction,
                             table_name='total',
                             arg='level',
                             page_number=1,
                             server_id=None):
    page_number = max(1, page_number)
    try:
        embed = await leaderboard_func(table_name, arg, page_number, server_id)
        if embed:
            view = LeaderboardView(interaction, table_name, arg, page_number, server_id)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=False)
        else:
            await interaction.response.send_message("Error, try again! \nMake sure the server has an assigned guild in 'infoportal-config'", ephemeral=True)
    except Exception as e:
        print(f"/lb error: {e}")
        await interaction.response.send_message("Error, server leaderboard not set! \nMake sure the server has an assigned guild in `infoportal-config`", ephemeral=True)


async def leaderboard_func(table_name, order, page_number, server_id=None):
    async with aiosqlite.connect('leaderboard.db') as conn:
        c = await conn.cursor()

        # Determine order field + validate inputs
        valid_orders = ['level', 'exp']
        valid_tables = SKILLS.copy()
        valid_tables.append('total')
        if order not in valid_orders:
            order = 'level'
        order2 = 'exp'
        if table_name == 'total' and order == 'level':
            order2 = 'level'
        table_name = table_name if table_name in valid_tables else 'total'
        guild_name = None
        guild_icon = None
        query = None
        parameters = None
        # Construct the basic or guild-specific SQL query based on the presence of server_id
        if server_id:
            # Connect to discord.db to fetch linked_guild
            async with aiosqlite.connect('discord.db') as discord_conn:
                discord_cursor = await discord_conn.cursor()
                await discord_cursor.execute(
                    "SELECT linked_guild FROM discord_servers WHERE server_id = ?;",
                    (server_id, )
                )
                guild_row = await discord_cursor.fetchone()
                # If linked_guild exists, use it to construct the second query
                if guild_row:
                    guild_id = guild_row[0]
                    await c.execute(
                        "SELECT * FROM guilds WHERE id = ?;",
                        (guild_id, )
                    )
                    guild_data = await c.fetchone()

                    query = f"""
                    SELECT u.username, u.{order}
                    FROM {table_name} u
                    JOIN guild_{guild_id} gm ON gm.user_id = u.user_id
                    ORDER BY u.{order2} DESC
                    LIMIT 10 OFFSET {10 * (page_number - 1)};
                    """
                    parameters = ()

                    if guild_data:
                        guild_name = guild_data[1]
                        guild_icon = guild_data[2]
                else: 
                    return None
                        

        else:
            query = f"""
            SELECT username, {order}
            FROM {table_name}
            ORDER BY {order2} DESC
            LIMIT 10 OFFSET {10 * (page_number - 1)};
            """
            parameters = ()

        # Execute query
        if query is None or parameters is None:
            return None
        await c.execute(query, parameters)
        # Create the embed for Discord
        title_prefix = f"{guild_name.title() + ' ' if (server_id and guild_name) else ''}"
        embed = discord.Embed(
            title=
            f"{title_prefix}{table_name.title()} {order.title()} Leaderboard",
            description="",
            color=0x00ff00)
        embed.set_footer(text=f"Page {page_number}")

        if guild_icon:
            embed.set_thumbnail(url="https:"+guild_icon + '?0.5060365238289637')

        if table_name != 'total':
            embed.set_thumbnail(url=ICON + table_name.lower() + ICON_END)

        # Process query results and add to embed
        medals = ["🥇 ", "🥈 ", "🥉 "]
        row_index = 0
        async for row in c:
            formatted_entry = f"{row[0]} - {'{:,}'.format(int(row[1]))}"
            if page_number == 1 and row_index < len(medals):
                formatted_entry = medals[row_index] + formatted_entry
            else:
                number = f"#{(page_number-1)*10 + row_index + 1} "
                formatted_entry = number + formatted_entry
            embed.add_field(name=formatted_entry, value="", inline=False)
            row_index += 1

        return embed
