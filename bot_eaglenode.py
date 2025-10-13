import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import subprocess
import random
import string
import os
from datetime import datetime, timedelta
from typing import Literal

# ========================
# CONFIG
# ========================
TOKEN = ""  # <-- add your bot token here
ADMIN_IDS = [1405778722732376176]
database_file = "database.txt"
PUBLIC_IP = "138.68.79.95"

# ========================
# DISCORD BOT SETUP
# ========================
intents = discord.Intents.default()
intents.messages = False
intents.message_content = False

bot = commands.Bot(command_prefix='/', intents=intents)


# ========================
# HELPER FUNCTIONS
# ========================
def is_admin(user_id):
    return user_id in ADMIN_IDS


def generate_random_string(length=6):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))


def add_to_database(user, container_name, ssh_command, ram, cpu, creator, os_type="Ubuntu 22.04"):
    with open(database_file, 'a') as f:
        f.write(f"{user}|{container_name}|{ssh_command}|{ram}|{cpu}|{creator}|{os_type}\n")


async def capture_ssh_session_line(process):
    while True:
        line = await process.stdout.readline()
        if not line:
            break
        decoded = line.decode('utf-8').strip()
        if "ssh session:" in decoded:
            return decoded.split("ssh session:")[1].strip()
    return None


def get_docker_image_for_os(os_type):
    os_map = {
        "ubuntu": "ubuntu-22.04-with-tmate",
        "debian": "debian-with-tmate"
    }
    return os_map.get(os_type, "ubuntu-22.04-with-tmate")


def os_type_to_display_name(os_type):
    os_map = {
        "ubuntu": "Ubuntu 22.04",
        "debian": "Debian 12"
    }
    return os_map.get(os_type, "Unknown OS")


# ========================
# SIMPLE /DEPLOY COMMAND
# ========================
@bot.tree.command(name="deploy", description="🚀 Admin: Deploy a new VPS instance for a user")
@app_commands.describe(
    user="Select the user to assign the VPS to",
    os="Operating system (ubuntu or debian)",
    ram="RAM in GB",
    cpu="CPU cores"
)
async def deploy_command(
    interaction: discord.Interaction,
    user: discord.User,
    os: Literal["ubuntu", "debian"],
    ram: int,
    cpu: int
):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return

    await interaction.response.defer()

    container_name = f"VPS_{user.name}_{generate_random_string()}"
    image = get_docker_image_for_os(os)

    try:
        # Create Docker container
        container_id = subprocess.check_output([
            "docker", "run", "-itd",
            "--privileged",
            "--cap-add=ALL",
            f"--memory={ram}g",
            f"--cpus={cpu}",
            "--hostname", "eaglenode",
            "--name", container_name,
            image
        ]).decode().strip()

        # Generate SSH session using tmate
        exec_cmd = await asyncio.create_subprocess_exec(
            "docker", "exec", container_name, "tmate", "-F",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        ssh_session_line = await capture_ssh_session_line(exec_cmd)

        if ssh_session_line:
            add_to_database(str(user), container_name, ssh_session_line, ram, cpu, str(interaction.user), os_type_to_display_name(os))

            embed = discord.Embed(
                title="✅ VPS Created Successfully!",
                description="Your VPS details are below. Keep them safe.",
                color=0x2400ff
            )
            embed.add_field(name="🧊 OS", value=os_type_to_display_name(os), inline=True)
            embed.add_field(name="💾 RAM", value=f"{ram} GB", inline=True)
            embed.add_field(name="🔥 CPU", value=f"{cpu} cores", inline=True)
            embed.add_field(name="🔑 SSH Command", value=f"```{ssh_session_line}```", inline=False)
            embed.add_field(name="🧠 Hostname", value="eaglenode", inline=True)
            embed.add_field(name="📦 Container Name", value=container_name, inline=False)

            try:
                await user.send(embed=embed)
                await interaction.followup.send(f"✅ VPS created and sent to {user.mention}", ephemeral=True)
            except discord.Forbidden:
                await interaction.followup.send(f"⚠️ VPS created, but I couldn’t DM {user.mention}.", ephemeral=True)
        else:
            await interaction.followup.send("❌ Failed to generate SSH session.", ephemeral=True)

    except subprocess.CalledProcessError as e:
        await interaction.followup.send(f"❌ Error creating container: {e}", ephemeral=True)


# ========================
# BASIC BOT EVENTS
# ========================
@bot.event
async def on_ready():
    print(f"🚀 Bot online as {bot.user}")
    await bot.tree.sync()
    await bot.change_presence(activity=discord.Game(name="EAGLENODE VPS"))


@bot.tree.command(name="ping", description="🏓 Check bot latency")
async def ping_command(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"🏓 Pong! `{latency}ms`")


# ========================
# RUN BOT
# ========================
bot.run(TOKEN)
