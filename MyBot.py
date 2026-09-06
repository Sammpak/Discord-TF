import os
import discord
from discord.ext import commands, tasks
from discord import app_commands
from dotenv import load_dotenv
import aiohttp
from urllib.parse import quote

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
RIOT_API_KEY = os.getenv("RIOT_API_KEY")
RIOT_ID = os.getenv("RIOT_ID")

# ──────────────────────────────────────────────
# FORCÉ SUR EUW
# ──────────────────────────────────────────────
PLATFORM = "euw1"
ROUTING = "europe"

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

listening = False
target_channel_id = None
target_user_id = None
was_in_game = False
player_puuid = None
last_game_id = None


# ──────────────────────────────────────────────
# Riot API helpers (EUW only)
# ──────────────────────────────────────────────

async def get_account_by_riot_id(session: aiohttp.ClientSession, game_name: str, tag_line: str):
    """Récupère le PUUID"""
    url = f"https://{ROUTING}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{quote(game_name)}/{quote(tag_line)}"
    headers = {"X-Riot-Token": RIOT_API_KEY}

    async with session.get(url, headers=headers) as resp:
        if resp.status == 200:
            return await resp.json()
        else:
            text = await resp.text()
            print(f"[Riot] Erreur {resp.status}: {text}")
            return None


async def is_in_game(session: aiohttp.ClientSession, puuid: str):
    """
    Check si le joueur est en partie.
    Retourne (True, gameId) si en jeu, sinon (False, None)
    """

    url = f"https://{PLATFORM}.api.riotgames.com/lol/spectator/v5/active-games/by-summoner/{puuid}"
    headers = {"X-Riot-Token": RIOT_API_KEY}

    async with session.get(url, headers=headers) as resp:
        if resp.status == 200:
            data = await resp.json()
            return True, data.get("gameId")
        elif resp.status == 404:
            return False, None
        else:
            text = await resp.text()
            print(f"[Spectator] Erreur {resp.status}: {text}")
            return False, None


# ──────────────────────────────────────────────
# Background task
# ──────────────────────────────────────────────

@tasks.loop(seconds=45)
async def check_game_status():
    global was_in_game, last_game_id

    if not listening or not player_puuid:
        return

    async with aiohttp.ClientSession() as session:
        in_game, game_id = await is_in_game(session, player_puuid)

        if in_game and not was_in_game:
            was_in_game = True
            last_game_id = game_id

            channel = bot.get_channel(target_channel_id)
            if channel:
                mention = f"<@{target_user_id}>" if target_user_id else ""
                await channel.send(
                    f"{mention} **{RIOT_ID}** vient de lancer une partie !\n"
                    f"`Game ID: {game_id}`"
                )
            print(f"[INFO] Partie détectée : GameID {game_id}")

        elif not in_game and was_in_game:
            was_in_game = False
            last_game_id = None
            print("[INFO] Partie terminée")


# ──────────────────────────────────────────────
# Slash commands
# ──────────────────────────────────────────────

@bot.tree.command(name="start_listening", description="Commence à écouter le Riot ID (EUW uniquement)")
@app_commands.describe(
    channel="Channel où envoyer le ping",
    user="Membre à ping"
)
async def start_listening(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    user: discord.Member = None
):
    global listening, target_channel_id, target_user_id, player_puuid, was_in_game

    await interaction.response.defer(ephemeral=True)

    if not RIOT_ID or "#" not in RIOT_ID:
        await interaction.followup.send("RIOT_ID mal configuré", ephemeral=True)
        return

    game_name, tag_line = RIOT_ID.split("#", 1)

    async with aiohttp.ClientSession() as session:
        account = await get_account_by_riot_id(session, game_name, tag_line)
        if not account:
            await interaction.followup.send(f"Impossible de trouver le compte `{RIOT_ID}`", ephemeral=True)
            return

        player_puuid = account["puuid"]
        print(f"[INFO] PUUID trouvé : {player_puuid}")

    target_channel_id = channel.id
    target_user_id = user.id if user else None
    was_in_game = False
    listening = True

    if not check_game_status.is_running():
        check_game_status.start()

    mention = f"<@{user.id}>" if user else "personne"
    await interaction.followup.send(
        f"Écoute activée pour **{RIOT_ID}** (EUW uniquement)\n"
        f"Channel : {channel.mention}\n"
        f"Ping : {mention}",
        ephemeral=True
    )


@bot.tree.command(name="stop_listening", description="Arrête l'écoute")
async def stop_listening(interaction: discord.Interaction):
    global listening
    listening = False
    if check_game_status.is_running():
        check_game_status.cancel()
    await interaction.response.send_message("Écoute arrêtée.", ephemeral=True)


@bot.tree.command(name="status", description="État actuel de l'écoute")
async def status(interaction: discord.Interaction):
    status_msg = (
        f"**Écoute active :** {listening}\n"
        f"**Riot ID :** `{RIOT_ID}`\n"
        f"**Région :** `EUW1`\n"
        f"**PUUID :** `{player_puuid}`\n"
        f"**En partie actuellement :** {was_in_game}"
    )
    await interaction.response.send_message(status_msg, ephemeral=True)


# ──────────────────────────────────────────────
# Events
# ──────────────────────────────────────────────

@bot.event
async def on_ready():
    print(f"{bot.user} is online!")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash command(s)")
    except Exception as e:
        print(f"Error syncing commands: {e}")


if __name__ == "__main__":
    if not TOKEN:
        print("[CRITICAL] DISCORD_TOKEN manquant")
    elif not RIOT_API_KEY:
        print("[CRITICAL] RIOT_API_KEY manquant")
    else:
        bot.run(TOKEN)