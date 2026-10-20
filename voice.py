#!/usr/bin/env python3
"""
Discord Voice Joiner / Sweet Voice 24/7
Automatically logs in using a User Token, retrieves a Voice Channel ID (or selects from a Server list) to hang out in voice 24/7.
Features:
- Receive tokens directly or via file/environment (tokens.json, .env, token.txt).
- Directly input the Voice Channel ID (paste ID to join directly without searching via servers).
- Visually browse the list of Servers & Voice Channels if an ID is not available.
- Automatically reconnects 24/7 (Anti-Kick / Auto-Reconnect on network loss, kicks, or AFK room moves).
- Options for Self-Mute, Self-Deafen, and Self-Video.
- Custom presence status configuration.
- Saves configuration to voice_config.json for automatic startup on subsequent runs.
"""

import os
import sys
import json
import time
import asyncio
import argparse
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple

# Silence excessively detailed default Discord logs
import logging
logging.getLogger("discord").setLevel(logging.WARNING)
logging.getLogger("discord.http").setLevel(logging.WARNING)
logging.getLogger("discord.client").setLevel(logging.WARNING)

# Set UTF-8 encoding for Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

try:
    from colorama import init, Fore, Style
    init(autoreset=True)
except ImportError:
    class Fore:
        GREEN = ""
        CYAN = ""
        YELLOW = ""
        RED = ""
        MAGENTA = ""
        WHITE = ""
        BLUE = ""
        RESET = ""
    class Style:
        BRIGHT = ""
        DIM = ""
        RESET_ALL = ""

try:
    import discord
except ImportError:
    print("Please install the required libraries:")
    print("pip install discord.py-self PyNaCl colorama python-dotenv")
    sys.exit(1)

from dotenv import load_dotenv
load_dotenv()

# Default configuration file
CONFIG_FILE = "voice_config.json"


# ── UI & Display Utilities ───────────────────────────────────────────────────
def print_banner():
    banner = f"""{Fore.CYAN}{Style.BRIGHT}
======================================================================
               DISCORD VOICE Joiner - VOICE Joiner 24/7              
            Automatically maintain continuous voice connection         
======================================================================{Style.RESET_ALL}"""
    print(banner)
    print(f"{Fore.YELLOW}[!] NOTE:{Style.RESET_ALL} Automating user tokens violates Discord ToS.")
    print(f"    Please use with caution and take full responsibility for your account.\n")


def log(msg: str, level: str = "info"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    badges = {
        "info": f"{Fore.CYAN}[INFO]{Style.RESET_ALL}",
        "ok": f"{Fore.GREEN}{Style.BRIGHT}[ OK ]{Style.RESET_ALL}",
        "warn": f"{Fore.YELLOW}[WARN]{Style.RESET_ALL}",
        "error": f"{Fore.RED}{Style.BRIGHT}[FAIL]{Style.RESET_ALL}",
        "time": f"{Fore.MAGENTA}[TIME]{Style.RESET_ALL}",
    }
    badge = badges.get(level, f"[{level.upper()}]")
    print(f"{Style.DIM}{timestamp}{Style.RESET_ALL} {badge} {msg}")


def format_duration(seconds: float) -> str:
    td = timedelta(seconds=int(seconds))
    days = td.days
    hours, remainder = divmod(td.seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    parts = []
    if days > 0:
        parts.append(f"{days} days")
    if hours > 0 or days > 0:
        parts.append(f"{hours:02d} hours")
    parts.append(f"{minutes:02d} minutes")
    parts.append(f"{secs:02d} seconds")
    return " ".join(parts)


async def ainput(prompt: str = "") -> str:
    """Read user input from terminal without blocking the asyncio loop."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, input, prompt)


# ── Configuration & Token Loading Management ─────────────────────────────────
def load_saved_config(config_path: str = CONFIG_FILE) -> Dict[str, Any]:
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log(f"Error reading configuration file {config_path}: {e}", "warn")
    return {}


def save_config(data: Dict[str, Any], config_path: str = CONFIG_FILE):
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        log(f"Configuration saved to {Fore.GREEN}{config_path}{Style.RESET_ALL}", "ok")
    except Exception as e:
        log(f"Failed to save configuration: {e}", "error")


def get_tokens_from_tokens_json() -> Dict[str, str]:
    if os.path.exists("tokens.json"):
        try:
            with open("tokens.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
    return {}


def get_token_from_env_or_files() -> Optional[str]:
    # 1. Environment variables
    env_token = os.getenv("USER_TOKEN") or os.getenv("DISCORD_TOKEN")
    if env_token:
        return env_token.strip().strip('"').strip("'")
    
    # 2. token.txt file
    if os.path.exists("token.txt"):
        try:
            with open("token.txt", "r", encoding="utf-8") as f:
                t = f.read().strip().strip('"').strip("'")
                if t:
                    return t
        except Exception:
            pass

    return None


# ── Main Voice Hanger Class ──────────────────────────────────────────────────
class VoiceJoiner:
    def __init__(self, config: Dict[str, Any], config_path: str = CONFIG_FILE):
        self.config = config
        self.config_path = config_path
        self.token: str = config.get("token", "")
        self.guild_id: Optional[int] = config.get("guild_id")
        self.channel_id: Optional[int] = config.get("channel_id")
        self.self_mute: bool = config.get("self_mute", True)
        self.self_deaf: bool = config.get("self_deaf", True)
        self.self_video: bool = config.get("self_video", False)
        self.auto_reconnect: bool = config.get("auto_reconnect", True)
        self.custom_status: str = config.get("custom_status", "Hanging out in Voice 24/7")

        self.voice_client: Optional[discord.VoiceClient] = None
        self.target_channel: Optional[discord.VoiceChannel] = None
        self.start_time: Optional[float] = None
        self.is_connected = False
        self.is_reconnecting = False
        self.is_shutting_down = False
        self.reconnect_cooldown = 5
        self.last_move_time = 0

        # Initialize Discord Client
        try:
            discord.opus._load_default()
        except Exception:
            pass

        self.client = discord.Client()
        self.register_events()

    def register_events(self):
        @self.client.event
        async def on_ready():
            log(f"Successfully logged in: {Fore.GREEN}{Style.BRIGHT}{self.client.user}{Style.RESET_ALL} (ID: {self.client.user.id})", "ok")
            log(f"Total servers the account is in: {Fore.CYAN}{len(self.client.guilds)}{Style.RESET_ALL}", "info")
            
            # Set Rich Presence status
            if self.custom_status:
                try:
                    activity = discord.CustomActivity(name=self.custom_status)
                    await self.client.change_presence(activity=activity, status=discord.Status.online)
                except Exception as e:
                    log(f"Could not set custom status: {e}", "warn")

            # Start setting up or directly join the voice channel
            asyncio.create_task(self.start_voice_session())

        @self.client.event
        async def on_voice_state_update(member, before, after):
            # Only track state changes for this account itself
            if member.id != self.client.user.id:
                return

            if self.is_shutting_down:
                return

            # Only handle disconnections after a successful prior connection
            if not self.is_connected:
                return

            # Case 1: Disconnected (kicked from voice or lost connection)
            if before.channel is not None and after.channel is None:
                self.is_connected = False
                log(f"Account was disconnected from the voice channel!", "warn")
                if self.auto_reconnect and not self.is_shutting_down and not self.is_reconnecting:
                    asyncio.create_task(self.delayed_reconnect())

            # Case 2: Moved to another channel (e.g., AFK room or another room)
            elif self.target_channel and after.channel and after.channel.id != self.target_channel.id:
                now = time.time()
                log(f"Detected being moved to another channel: {Fore.YELLOW}{after.channel.name}{Style.RESET_ALL}", "warn")
                
                # Avoid infinite loops if continuously moved
                if now - self.last_move_time > 5 and self.auto_reconnect and not self.is_reconnecting:
                    self.last_move_time = now
                    asyncio.create_task(self.move_back_to_target())

    async def resolve_channel_by_id(self, channel_id: int) -> Optional[discord.VoiceChannel]:
        """Find voice channel by ID (via cache or direct fetch_channel call)."""
        ch = self.client.get_channel(channel_id)
        if not ch:
            try:
                ch = await self.client.fetch_channel(channel_id)
            except Exception as e:
                log(f"Could not find channel ID {channel_id}: {e}", "warn")
                return None

        if not isinstance(ch, (discord.VoiceChannel, discord.StageChannel)):
            log(f"Channel ID {channel_id} ('{getattr(ch, 'name', 'N/A')}') is not a Voice/Stage channel!", "err")
            return None

        return ch

    async def start_voice_session(self):
        """Start the voice hanging session: check pre-existing channel_id or prompt for interactive selection."""
        try:
            # If the user provided a channel_id (from arguments, config, or initial prompt)
            if self.channel_id:
                ch = await self.resolve_channel_by_id(int(self.channel_id))
                if ch:
                    self.target_channel = ch
                    self.guild_id = ch.guild.id
                    log(f"Identified Voice Channel: {Fore.GREEN}{Style.BRIGHT}{ch.name}{Style.RESET_ALL} (Server: {ch.guild.name})", "ok")
                else:
                    log(f"Voice ID {self.channel_id} not found or account is not in this server!", "err")
                    self.channel_id = None
                    self.target_channel = None

            # If no valid target voice channel, switch to selection menu
            if not self.target_channel:
                await self.interactive_selection()

            if not self.target_channel:
                log("No voice channel selected. Stopping session.", "err")
                await self.client.close()
                return

            # Proceed to connect to the target channel
            await self.connect_to_target()

            # Run uptime monitor loop
            asyncio.create_task(self.uptime_monitor_loop())

        except Exception as e:
            log(f"Error during voice session initialization: {e}", "err")

    async def interactive_selection(self):
        """Voice Channel selection menu: supports pasting Channel ID directly or browsing Server -> Channel list."""
        print(f"\n{Fore.YELLOW}{Style.BRIGHT}================== SELECT VOICE CHANNEL TO Join =================={Style.RESET_ALL}")
        print("You can choose 1 of 2 ways:")
        print(f"  [{Fore.CYAN}1{Style.RESET_ALL}] Paste Voice Channel ID directly (fastest)")
        print(f"  [{Fore.CYAN}2{Style.RESET_ALL}] Browse Server & Voice Channel list to select")
        print("Tip: Enable Developer Mode (Settings -> Advanced -> Developer Mode),")
        print("then right-click the voice channel -> select 'Copy Channel ID'.\n")

        prompt = "> Paste Voice Channel ID (or press Enter / type '2' to view Server list): "
        choice = (await ainput(prompt)).strip()

        # If user pasted a Voice Channel ID (digits with 15+ characters)
        if choice.isdigit() and len(choice) >= 15:
            cid = int(choice)
            log(f"Checking Voice Channel ID {cid}...", "info")
            ch = await self.resolve_channel_by_id(cid)
            if ch:
                self.target_channel = ch
                self.channel_id = ch.id
                self.guild_id = ch.guild.id
                log(f"Found Channel: {Fore.GREEN}{Style.BRIGHT}{ch.name}{Style.RESET_ALL} (Server: {ch.guild.name})", "ok")
                await self.prompt_voice_options(ch.guild, ch)
                return
            else:
                log(f"Could not connect to ID {cid}. Switching to Server list...", "warn")

        # Browse Server -> Voice Channel list
        await self.select_from_server_list()

    async def select_from_server_list(self):
        """Browse and select Server, then select Voice Channel."""
        print(f"\n{Fore.YELLOW}{Style.BRIGHT}---------- STEP 1: SELECT SERVER ----------{Style.RESET_ALL}")
        guilds = list(self.client.guilds)
        if not guilds:
            log("Your account is not in any servers!", "err")
            return

        for idx, guild in enumerate(guilds, 1):
            member_count = guild.member_count or "N/A"
            print(f"  [{Fore.CYAN}{idx:02d}{Style.RESET_ALL}] {Fore.WHITE}{Style.BRIGHT}{guild.name}{Style.RESET_ALL} (ID: {guild.id}) - {member_count} members")

        selected_guild = None
        while not selected_guild:
            prompt = f"\n> Enter server index number (1-{len(guilds)}) or paste Server ID: "
            user_choice = (await ainput(prompt)).strip()

            if user_choice.isdigit():
                val = int(user_choice)
                if 1 <= val <= len(guilds):
                    selected_guild = guilds[val - 1]
                else:
                    selected_guild = self.client.get_guild(val)
            else:
                for g in guilds:
                    if g.name.lower() == user_choice.lower():
                        selected_guild = g
                        break

            if not selected_guild:
                print(f"{Fore.RED}Invalid selection, please try again.{Style.RESET_ALL}")

        self.guild_id = selected_guild.id
        log(f"Selected server: {Fore.GREEN}{Style.BRIGHT}{selected_guild.name}{Style.RESET_ALL}", "ok")

        # Select Voice Channel in the chosen server
        print(f"\n{Fore.YELLOW}{Style.BRIGHT}---------- STEP 2: SELECT VOICE CHANNEL ----------{Style.RESET_ALL}")
        voice_channels = [
            c for c in selected_guild.channels
            if isinstance(c, (discord.VoiceChannel, discord.StageChannel))
        ]
        voice_channels.sort(key=lambda c: c.position)

        if not voice_channels:
            log(f"Server '{selected_guild.name}' has no voice channels or the account lacks view permissions!", "err")
            return

        for idx, vc in enumerate(voice_channels, 1):
            channel_type = "[Stage]" if isinstance(vc, discord.StageChannel) else "[Voice]"
            user_count = len(vc.members)
            limit_str = f"/{vc.user_limit}" if getattr(vc, 'user_limit', 0) > 0 else ""
            category_name = f"[{vc.category.name}] " if vc.category else ""
            
            permissions = vc.permissions_for(selected_guild.me)
            lock_str = "" if permissions.connect else f" {Fore.RED}[Locked - Missing Permission]{Style.RESET_ALL}"

            print(f"  [{Fore.CYAN}{idx:02d}{Style.RESET_ALL}] {channel_type} {Fore.WHITE}{category_name}{vc.name}{Style.RESET_ALL} ({user_count}{limit_str} people){lock_str} (ID: {vc.id})")

        selected_channel = None
        while not selected_channel:
            prompt = f"\n> Enter voice channel index number (1-{len(voice_channels)}) or paste Channel ID: "
            user_choice = (await ainput(prompt)).strip()

            if user_choice.isdigit():
                val = int(user_choice)
                if 1 <= val <= len(voice_channels):
                    selected_channel = voice_channels[val - 1]
                else:
                    selected_channel = selected_guild.get_channel(val)
            else:
                for vc in voice_channels:
                    if vc.name.lower() == user_choice.lower():
                        selected_channel = vc
                        break

            if not selected_channel:
                print(f"{Fore.RED}Invalid selection, please try again.{Style.RESET_ALL}")

        self.channel_id = selected_channel.id
        self.target_channel = selected_channel
        log(f"Selected channel: {Fore.GREEN}{Style.BRIGHT}{selected_channel.name}{Style.RESET_ALL}", "ok")

        await self.prompt_voice_options(selected_guild, selected_channel)

    async def prompt_voice_options(self, guild: discord.Guild, channel: discord.VoiceChannel):
        """Ask user for Mute, Deafen, Camera, Custom Status options and save configuration."""
        print(f"\n{Fore.YELLOW}{Style.BRIGHT}---------- STEP 3: SETTINGS OPTIONS ----------{Style.RESET_ALL}")
        mute_ans = (await ainput("Automatically Mute Microphone (Self-Mute)? [Y/n]: ")).strip().lower()
        self.self_mute = mute_ans in ("", "y", "yes", "true", "1")

        deaf_ans = (await ainput("Automatically Deafen Headset (Self-Deafen)? [Y/n]: ")).strip().lower()
        self.self_deaf = deaf_ans in ("", "y", "yes", "true", "1")

        video_ans = (await ainput("Turn on Camera (Self-Video)? [y/N]: ")).strip().lower()
        self.self_video = video_ans in ("y", "yes", "true", "1")

        status_input = (await ainput("Enter display status (Press Enter to use 'Joining out in Voice 24/7'): ")).strip()
        if status_input:
            self.custom_status = status_input

        # Save configuration
        save_ans = (await ainput("\nDo you want to save this configuration for future runs? [Y/n]: ")).strip().lower()
        if save_ans in ("", "y", "yes", "true", "1"):
            config_data = {
                "token": self.token,
                "guild_id": guild.id,
                "guild_name": guild.name,
                "channel_id": channel.id,
                "channel_name": channel.name,
                "self_mute": self.self_mute,
                "self_deaf": self.self_deaf,
                "self_video": self.self_video,
                "auto_reconnect": self.auto_reconnect,
                "custom_status": self.custom_status,
            }
            save_config(config_data, self.config_path)

    async def connect_to_target(self):
        """Connect to the target voice channel."""
        if not self.target_channel:
            log("No target voice channel specified to connect!", "err")
            return

        log(f"Connecting to channel {Fore.CYAN}{Style.BRIGHT}{self.target_channel.name}{Style.RESET_ALL} (Server: {self.target_channel.guild.name})...", "info")

        # Disconnect old voice clients if any
        for vc in list(self.client.voice_clients):
            try:
                await vc.disconnect(force=True)
            except Exception:
                pass

        try:
            self.voice_client = await self.target_channel.connect(
                timeout=30.0,
                reconnect=True,
                self_deaf=self.self_deaf,
                self_mute=self.self_mute
            )
            self.is_connected = True
            if self.start_time is None:
                self.start_time = time.time()

            mute_status = f"{Fore.GREEN}ON{Style.RESET_ALL}" if self.self_mute else f"{Fore.RED}OFF{Style.RESET_ALL}"
            deaf_status = f"{Fore.GREEN}ON{Style.RESET_ALL}" if self.self_deaf else f"{Fore.RED}OFF{Style.RESET_ALL}"
            video_status = f"{Fore.GREEN}ON{Style.RESET_ALL}" if self.self_video else f"{Fore.RED}OFF{Style.RESET_ALL}"

            print(f"\n{Fore.GREEN}{Style.BRIGHT}======================================================================")
            print(f"               SUCCESSFULLY CONNECTED TO VOICE ROOM!              ")
            print(f"======================================================================{Style.RESET_ALL}")
            print(f"  * Server         : {Fore.WHITE}{Style.BRIGHT}{self.target_channel.guild.name}{Style.RESET_ALL}")
            print(f"  * Voice Room     : {Fore.CYAN}{Style.BRIGHT}{self.target_channel.name}{Style.RESET_ALL} (ID: {self.target_channel.id})")
            print(f"  * Self-Mute      : {mute_status}")
            print(f"  * Self-Deafen    : {deaf_status}")
            print(f"  * Camera Video   : {video_status}")
            print(f"  * Auto-Reconnect : {Fore.GREEN}ENABLED (24/7 Anti-Kick){Style.RESET_ALL}")
            print(f"  * Press {Fore.YELLOW}Ctrl + C{Style.RESET_ALL} at any time to stop and safely disconnect.\n")

        except Exception as e:
            self.is_connected = False
            log(f"Error connecting to voice channel: {e}", "err")
            if self.auto_reconnect and not self.is_shutting_down and not self.is_reconnecting:
                asyncio.create_task(self.delayed_reconnect())

    async def delayed_reconnect(self):
        """Delayed reconnection to avoid conflicts with the Discord Gateway."""
        if self.is_reconnecting or self.is_shutting_down:
            return
        self.is_reconnecting = True
        try:
            log(f"Will attempt to reconnect in {self.reconnect_cooldown} seconds...", "warn")
            await asyncio.sleep(self.reconnect_cooldown)
            log("Proceeding to reconnect to the voice channel...", "info")
            await self.connect_to_target()
        finally:
            self.is_reconnecting = False

    async def move_back_to_target(self):
        """Move back to the target room if transferred to another channel (such as AFK channel)."""
        log(f"Automatically moving back to target channel: {Fore.CYAN}{self.target_channel.name}{Style.RESET_ALL}...", "info")
        await asyncio.sleep(2)
        try:
            guild = self.client.get_guild(self.guild_id)
            if guild:
                await guild.change_voice_state(
                    channel=self.target_channel,
                    self_mute=self.self_mute,
                    self_deaf=self.self_deaf,
                    self_video=self.self_video
                )
        except Exception as e:
            log(f"Error moving back to channel: {e}. Trying to reconnect...", "warn")
            await self.connect_to_target()

    async def uptime_monitor_loop(self):
        """Loop to display hanging uptime and monitor connection status periodically."""
        iteration = 0
        while not self.is_shutting_down:
            await asyncio.sleep(15)
            iteration += 1
            if self.is_connected and self.start_time:
                uptime_str = format_duration(time.time() - self.start_time)
                ping_ms = round(self.client.latency * 1000, 1) if self.client.latency else 0
                
                # Print status info every 60 seconds (every 4 cycles of 15s)
                if iteration % 4 == 0:
                    channel_name = self.target_channel.name if self.target_channel else "N/A"
                    members_count = len(self.target_channel.members) if self.target_channel else 0
                    log(f"⏱️  Uptime: {Fore.GREEN}{Style.BRIGHT}{uptime_str}{Style.RESET_ALL} | Ping: {ping_ms}ms | Room: {channel_name} ({members_count} people)", "time")

    async def shutdown(self):
        """Cleanup and safely disconnect when closing the application."""
        if self.is_shutting_down:
            return
        self.is_shutting_down = True
        print(f"\n{Fore.YELLOW}Disconnecting from voice channel and closing session...{Style.RESET_ALL}")
        
        for vc in list(self.client.voice_clients):
            try:
                await vc.disconnect(force=True)
            except Exception:
                pass
                
        await self.client.close()
        total_time = format_duration(time.time() - self.start_time) if self.start_time else "0 seconds"
        log(f"Safely disconnected. Total uptime: {Fore.CYAN}{total_time}{Style.RESET_ALL}", "ok")


# ── Main Function & Startup ──────────────────────────────────────────────────
def parse_arguments():
    parser = argparse.ArgumentParser(description="Discord Voice Hanger / Voice Joiner 24/7")
    parser.add_argument("--token", help="Discord User Token")
    parser.add_argument("--guild", type=int, help="ID of the Server to hang in")
    parser.add_argument("--channel", type=int, help="ID of the Voice Channel to hang in (input ID to join directly)")
    parser.add_argument("--config", default=CONFIG_FILE, help=f"Config file path (default: {CONFIG_FILE})")
    parser.add_argument("--setup", action="store_true", help="Force interactive configuration menu")
    parser.add_argument("--mute", type=str, choices=["true", "false"], help="Enable/disable self-mute (true/false)")
    parser.add_argument("--deaf", type=str, choices=["true", "false"], help="Enable/disable self-deafen (true/false)")
    parser.add_argument("--status", type=str, help="Custom Status")
    return parser.parse_args()


def select_or_input_token(saved_token: Optional[str]) -> str:
    """Support token selection from tokens.json, old config, or manual entry."""
    tokens_from_file = get_tokens_from_tokens_json()

    print(f"\n{Fore.YELLOW}{Style.BRIGHT}================== DISCORD TOKEN LOGIN =================={Style.RESET_ALL}")
    
    # If tokens found in tokens.json
    if tokens_from_file:
        print("Found saved accounts in tokens.json:")
        token_list = list(tokens_from_file.items())
        for idx, (uid, tok) in enumerate(token_list, 1):
            tok_preview = f"{tok[:10]}...{tok[-5:]}" if len(tok) > 15 else tok
            print(f"  [{Fore.CYAN}{idx}{Style.RESET_ALL}] User ID: {Fore.WHITE}{Style.BRIGHT}{uid}{Style.RESET_ALL} (Token: {tok_preview})")
        print(f"  [{Fore.CYAN}0{Style.RESET_ALL}] Manually enter a new Token")

        if saved_token:
            sav_preview = f"{saved_token[:10]}...{saved_token[-5:]}" if len(saved_token) > 15 else saved_token
            print(f"  [Enter] Use previously configured token: ({sav_preview})")

        choice = input("\n> Your choice: ").strip()
        if choice == "" and saved_token:
            return saved_token
        if choice.isdigit():
            c_val = int(choice)
            if 1 <= c_val <= len(token_list):
                return token_list[c_val - 1][1]

    # If token from old config file
    elif saved_token:
        sav_preview = f"{saved_token[:10]}...{saved_token[-5:]}" if len(saved_token) > 15 else saved_token
        print(f"Saved token: {Fore.GREEN}{sav_preview}{Style.RESET_ALL}")
        choice = input("> Press Enter to keep using this token, or type 'new' to enter a new token [Enter/new]: ").strip().lower()
        if choice not in ("new", "n", "change"):
            return saved_token

    # Manually enter a new token
    while True:
        token_input = input("> Enter your Discord User Token: ").strip().strip('"').strip("'")
        if token_input:
            return token_input
        print(f"{Fore.RED}Token cannot be empty! Please re-enter.{Style.RESET_ALL}")


def select_or_input_channel_id(saved_channel_id: Optional[int], saved_guild_name: str, saved_channel_name: str) -> Optional[int]:
    """Support direct Voice Channel ID input or reusing saved ID."""
    if saved_channel_id:
        print(f"\n{Fore.YELLOW}{Style.BRIGHT}================== SAVED VOICE CHANNEL =================={Style.RESET_ALL}")
        print(f"  * Server       : {Fore.GREEN}{saved_guild_name}{Style.RESET_ALL}")
        print(f"  * Voice Channel: {Fore.CYAN}{saved_channel_name}{Style.RESET_ALL} (ID: {saved_channel_id})")
        print("\nYou can:")
        print(f"  - Press {Fore.GREEN}Enter{Style.RESET_ALL} to join this channel immediately.")
        print(f"  - Paste a {Fore.CYAN}new Voice Channel ID{Style.RESET_ALL} to switch channels.")
        print(f"  - Type {Fore.YELLOW}'list'{Style.RESET_ALL} to browse the Server & Channel list after logging in.")

        val = input("\n> Choice [Enter/Paste ID/list]: ").strip()
        if val == "":
            return saved_channel_id
        if val.isdigit() and len(val) >= 15:
            return int(val)
        if val.lower() in ("list", "menu", "n", "new"):
            return None

    # No saved ID
    print(f"\n{Fore.YELLOW}{Style.BRIGHT}================== ENTER VOICE CHANNEL ID =================={Style.RESET_ALL}")
    print("Tip: Right-click a Voice Channel on Discord -> Select 'Copy Channel ID'.")
    val = input("> Paste Voice Channel ID (or press Enter / type 'list' to view Server & Channel list): ").strip()
    if val.isdigit() and len(val) >= 15:
        return int(val)
    return None


def main():
    args = parse_arguments()
    print_banner()

    # 1. Load configuration from file
    saved_config = load_saved_config(args.config)

    # 2. Determine token
    token = args.token
    if not token and not args.setup:
        token = saved_config.get("token") or get_token_from_env_or_files()

    if not token or args.setup:
        token = select_or_input_token(saved_config.get("token"))

    # 3. Determine Voice Channel ID
    channel_id = args.channel
    guild_id = args.guild

    if channel_id is None and not args.setup:
        saved_cid = saved_config.get("channel_id")
        saved_gname = saved_config.get("guild_name", "N/A")
        saved_cname = saved_config.get("channel_name", "N/A")
        channel_id = select_or_input_channel_id(saved_cid, saved_gname, saved_cname)
        if channel_id == saved_cid:
            guild_id = saved_config.get("guild_id")
    elif args.setup:
        channel_id = select_or_input_channel_id(None, "", "")

    # 4. Merge configuration
    config = {
        "token": token,
        "guild_id": guild_id,
        "channel_id": channel_id,
        "self_mute": (args.mute.lower() == "true") if args.mute else saved_config.get("self_mute", True),
        "self_deaf": (args.deaf.lower() == "true") if args.deaf else saved_config.get("self_deaf", True),
        "self_video": saved_config.get("self_video", False),
        "auto_reconnect": saved_config.get("auto_reconnect", True),
        "custom_status": args.status or saved_config.get("custom_status", "Hanging out in Voice 24/7"),
    }

    Joiner = VoiceJoiner(config, config_path=args.config)

    # Run Discord client
    try:
        Joiner.client.run(token)
    except discord.errors.LoginFailure:
        log("Invalid token or account password changed/session expired!", "err")
        log("Please check your token and try again.", "err")
    except KeyboardInterrupt:
        pass
    except Exception as e:
        log(f"Unknown error: {e}", "err")
    finally:
        print(f"\n{Fore.CYAN}Thank you for using Discord Voice Joiner! Goodbye!{Style.RESET_ALL}")


if __name__ == "__main__":
    main()