import os
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
import asyncio
import aiohttp

import json
import requests

# Load token
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")


# Intents
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Load codes from file
with open("ALLCODESRUST.txt", "r") as f:
    all_codes = [line.strip() for line in f if line.strip()]

available_codes = all_codes.copy()
reserved_codes = {} 

# #######################
# START BOT
# #######################


@bot.event
async def on_ready():
    print(f"{bot.user} is online!")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash command(s)")
    except Exception as e:
        print(f"Error syncing commands: {e}")


# #######################
# RUST RAID
# #######################


@bot.tree.command(name="coderaid", description="Attribue un code à raid depuis la liste")
async def random_number(interaction: discord.Interaction):
    global available_codes, reserved_codes

    if not available_codes:
        await interaction.response.send_message("✅ Tous les codes ont été attribués.", ephemeral=True)
        return

    user = interaction.user
    await interaction.response.defer()

    while available_codes:
        code = available_codes.pop(0)

        placeholder = await interaction.followup.send(f"{user.mention} Ton code : **{code}**", wait=True)
        await asyncio.sleep(1)
        await placeholder.add_reaction("✅") 

        reserved_codes[placeholder.id] = code

        def check(reaction, reacting_user):
            return (
                reaction.message.id == placeholder.id and
                str(reaction.emoji) in ["✅", "🗿"] and
                not reacting_user.bot
            )

        try:
            reaction, reacting_user = await bot.wait_for("reaction_add", timeout=600.0, check=check)

            if str(reaction.emoji) == "✅":
                print(f"[LOG] {reacting_user.name} a validé le code : {code}")
                del reserved_codes[placeholder.id]
                await placeholder.delete()

            elif str(reaction.emoji) == "🗿":
                await interaction.channel.send(f"@everyone Le code de la base est : **{code}**")
                print(f"[ALERTE] {reacting_user.name} a signalé le code comme celui de la base : {code}")
                del reserved_codes[placeholder.id]
                await placeholder.delete()

        except asyncio.TimeoutError:
            print(f"[LOG] Code {code} non validé → remis en circulation.")
            available_codes.insert(0, code)
            del reserved_codes[placeholder.id]
            await placeholder.delete()
            break

    if not available_codes:
        await interaction.followup.send("✅ Tous les codes ont été utilisés.")


@bot.tree.command(name="resetcodes", description="Réinitialise tous les codes depuis le fichier")
async def reset_codes(interaction: discord.Interaction):
    global available_codes, reserved_codes, all_codes

    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Seuls les administrateurs peuvent réinitialiser les codes.", ephemeral=True)
        return

    try:
        with open("ALLCODESRUST.txt", "r") as f:
            all_codes = [line.strip() for line in f if line.strip()]
        available_codes = all_codes.copy()
        reserved_codes.clear()
        await interaction.response.send_message("🔁 Tous les codes ont été réinitialisés.") 
        print("[LOG] Les codes ont été réinitialisés par un administrateur.")
    except Exception as e:
        await interaction.response.send_message(f"Erreur lors du chargement : {e}")


@bot.tree.command(name="nbcodes", description="Affiche le nombre de codes disponibles")
async def show_code_counts(interaction: discord.Interaction):
    global available_codes, reserved_codes, all_codes

    total = len(all_codes)
    dispo = len(available_codes)
    reserves = len(reserved_codes)

    await interaction.response.send_message(
        f"**État des codes :**\n"
        f"Disponibles : `{dispo}`\n"
        f"Réservés : `{reserves}`\n"
        f"Total : `{total}`"
    )

# Start the bot
print(f"[DEBUG] TOKEN: {TOKEN}")
try:
    bot.run(TOKEN)
except Exception as e:
    print(f"[CRITICAL ERROR] Le bot n’a pas pu démarrer : {e}")