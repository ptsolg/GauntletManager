import discord
import asyncio
import uuid
import re
import pygsheets
import json
import os
from datetime import datetime, timedelta
from discord import File, User, Member
from discord.ext import commands
from discord.ext.commands import UserConverter
from challenge import Context, BotErr
from xlsx import DefaultWriter, GoogleSheetsWriter, XlsxExporter
from enum import Enum

bot = commands.Bot(command_prefix='!')
bot.remove_command('help')
ctx = Context(challenges={}, users={})
gsheets_client = None
spreadsheet = None

class Privelege(Enum):
	ADMIN = 0
	USER = 1

def check_cmd_ctx(cmd_ctx, privilege_level = Privelege.ADMIN):
	author = cmd_ctx.message.author
	if type(author) is not Member:
		raise Exception('PMs are not allowed.')

	if privilege_level == Privelege.ADMIN:
		if 'bot commander' not in map(lambda x: x.name.lower(), cmd_ctx.message.author.roles):
			raise BotErr('"Bot Commander" role required.')

def save():
	open('challenges.json', 'w').write(ctx.to_json())

def load():
	global ctx
	data = json.loads(open('challenges.json', 'r').read())
	ctx = Context.from_json(data)

@bot.command()
async def start_challenge(cmd_ctx, name: str):
	try:
		check_cmd_ctx(cmd_ctx)
		ctx.start_challenge(name, cmd_ctx.message.channel.id)
		save()
		await cmd_ctx.send('Challenge "{}" has been created.'.format(name))
	except BotErr as e:
		await cmd_ctx.send(e)

@bot.command()
async def end_challenge(cmd_ctx):
	try:
		check_cmd_ctx(cmd_ctx)
		challenge = ctx.current_challenge
		ctx.end_challenge()
		save()
		await cmd_ctx.send('Challenge "{}" has been ended.'.format(challenge))
	except BotErr as e:
		await cmd_ctx.send(e)

@bot.command()
async def add_pool(cmd_ctx, name: str):
	try:
		check_cmd_ctx(cmd_ctx)
		ctx.add_pool(name)
		save()
		await cmd_ctx.send('Pool "{}" has been created.'.format(name))
	except BotErr as e:
		await cmd_ctx.send(e)

@bot.command()
async def add_user(cmd_ctx, user: UserConverter):
	try:
		check_cmd_ctx(cmd_ctx)
		ctx.add_user(user)
		save()
		await cmd_ctx.send('User {} has been added.'.format(user.mention))
	except BotErr as e:
		await cmd_ctx.send(e)

@bot.command()
async def set_color(cmd_ctx, *args):
	try:
		privilege_level = Privelege.USER
		user = cmd_ctx.message.author
		color = '#FFFFFF'

		if len(args) > 1:
			user = args[0]
			color = args[1]
			privilege_level = Privelege.ADMIN
		elif len(args) == 1:
			color = args[0]

		check_cmd_ctx(cmd_ctx, privilege_level)
		if re.match(r'^#[a-fA-F0-9]{6}$', color) is None:
			return await cmd_ctx.send('Invalid color "{}".'.format(color))
		ctx.set_color(user, color)
		save()
		await cmd_ctx.send('Color has been changed.')
	except BotErr as e:
		await cmd_ctx.send(e)

@bot.command()
async def sync(cmd_ctx):
	XlsxExporter(GoogleSheetsWriter(spreadsheet), ctx).export()
	await cmd_ctx.send('Done.')

async def user_or_none(cmd_ctx, s):
	try:
		return await UserConverter().convert(cmd_ctx, s)
	except:
		return None

async def _add_title(cmd_ctx, pool: str, proposer: User, title_name: str, title_url: str):
	try:
		check_cmd_ctx(cmd_ctx)
		ctx.add_title(pool, proposer, title_name, title_url)
		save()
		await cmd_ctx.send('Title "{}" has been added to "{}" pool.'.format(title_name, pool))
	except BotErr as e:
		await cmd_ctx.send(e)

@bot.command()
async def add_title(cmd_ctx, *args):
	if len(args) < 2 or len(args) > 4:
		return

	name_pos = 1
	pool = 'main'
	title_url = None
	user = await user_or_none(cmd_ctx, args[0])
	title_name = args[1]

	if user is None:
		if len(args) < 3:
			return
		if len(args) == 4:
			title_url = args[-1]
		pool = args[0]
		title_name = args[2]
		user = await UserConverter().convert(cmd_ctx, args[1])
	elif len(args) == 3:
		title_url = args[-1]

	await _add_title(cmd_ctx, pool, user, title_name, title_url)

@bot.command()
async def start_round(cmd_ctx, length: int):
	try:
		check_cmd_ctx(cmd_ctx)
		ctx.start_round(timedelta(days=length))
		save()
		rounds = ctx.current().rounds
		await cmd_ctx.send('Round {} ({}-{}) starts right now.'.format(len(rounds) - 1, rounds[-1].begin, rounds[-1].end))
	except BotErr as e:
		await cmd_ctx.send(e)

async def _end_round(channel):
	try:
		ctx.end_round()
		save()
		rounds = ctx.current().rounds
		await channel.send('Round {} has been ended.'.format(len(rounds) - 1))
	except BotErr as e:
		await channel.send(e)

@bot.command()
async def end_round(cmd_ctx):
	try:
		check_cmd_ctx(cmd_ctx)
		await _end_round(cmd_ctx.message.channel)
	except BotErr as e:
		await channel.send(e)

@bot.command()
async def rate(cmd_ctx, *args):
	try:
		user = cmd_ctx.message.author
		score = 0.0

		if len(args) < 1 or len(args) > 2:
			await cmd_ctx.send('Ivalid number of arguments({}). !rate <user> score'.format(len(args)))
			return

		privilege_level = Privelege.USER

		if len(args) > 1:
			privilege_level = Privelege.ADMIN
			user = args[0]
			score = float(args[1])
		else:
			score = float(args[0])

		if score < 0.0 or score > 10.0:
			await cmd_ctx.send('Score must be in range from 0 to 10')
			return

		check_cmd_ctx(cmd_ctx, privilege_level)
		ctx.rate(user, score)
		save()
		title = ctx.current().last_round().rolls[user.id].title
		await cmd_ctx.send('User {} gave {} to "{}".'.format(user.mention, score, title))
	except BotErr as e:
		await cmd_ctx.send(e)

@bot.command()
async def reroll(cmd_ctx, *args):
	try:
		user = cmd_ctx.message.author
		pool = 'main'

		if len(args) > 0:
			user = args[0]

		if len(args) > 1:
			pool = args[1]

		check_cmd_ctx(cmd_ctx)
		title = ctx.reroll(user, pool)
		save()
		await cmd_ctx.send('User {} rolled "{}" from "{}" pool.'.format(user.mention, title, pool))
	except BotErr as e:
		await cmd_ctx.send(e)

@bot.command()
async def rename_title(cmd_ctx, old_title: str, new_title: str):
	try:
		check_cmd_ctx(cmd_ctx)
		ctx.rename_title(old_title, new_title)
		save()
		await cmd_ctx.send('Title {} has been renamed to {}.'.format(old_title, new_title))
	except BotErr as e:
		await cmd_ctx.send(e)

@bot.command()
async def remove_user(cmd_ctx, user: UserConverter):
	try:
		check_cmd_ctx(cmd_ctx)
		ctx.remove_user(user)
		save()
		await cmd_ctx.send('User {} has been removed.'.format(user.mention))
	except BotErr as e:
		await cmd_ctx.send(e)

@bot.command()
async def remove_title(cmd_ctx, title: str):
	try:
		check_cmd_ctx(cmd_ctx)
		ctx.remove_title(title)
		save()
		await cmd_ctx.send('Title "{}" has been removed'.format(title))
	except BotErr as e:
		await cmd_ctx.send(e)

@bot.command()
async def remove_pool(cmd_ctx, pool: str):
	try:
		check_cmd_ctx(cmd_ctx)
		ctx.remove_pool(pool)
		save()
		await cmd_ctx.send('Pool "{}" has been removed'.format(pool))
	except BotErr as e:
		await cmd_ctx.send(e)

@bot.command()
async def extend_round(cmd_ctx, days: int):
	try:
		check_cmd_ctx(cmd_ctx)
		ctx.extend_round(timedelta(days=days))
		save()
		rounds = ctx.current().rounds
		await cmd_ctx.send('Round {} ends at {}.'.format(len(rounds) - 1, rounds[-1].end))
	except BotErr as e:
		await cmd_ctx.send(e)

@bot.command()
async def export(cmd_ctx, ext: str):
	fname = str(uuid.uuid4())
	if ext == 'xlsx':
		fname += '.xlsx'
		XlsxExporter(DefaultWriter(fname), ctx).export()
	elif ext == 'json':
		fname += '.json'
		open(fname, 'w').write(ctx.to_json())
	else:
		return await cmd_ctx.send('Unknown format "{}" (use xlsx or json).'.format(ext))

	await cmd_ctx.send(file=File(fname))
	os.remove(fname)

@bot.command()
async def help(cmd_ctx):
	await cmd_ctx.send('''
		!start_challenge name
		!add_pool name
		!add_user @user
		!add_title pool @user title_name title_url
		!start_round days
		!end_round
		!rate @user score
		!reroll @user pool
		!export
	''')

async def check_deadline():
	await bot.wait_until_ready()
	while not bot.is_closed():
		try:
			challenge = ctx.current()
			rnd = challenge.last_round()
			if datetime.now() >= rnd.parse_end():
				await _end_round(bot.get_channel(challenge.channel_id))
		except:
			pass
		await asyncio.sleep(10)

if __name__ == '__main__':
	try:
		load()
	except Exception as e:
		print(str(e))

	gsheets_client = pygsheets.authorize('client_secret.json')
	spreadsheet = gsheets_client.open_by_key('some key')
	bot.loop.create_task(check_deadline())
	bot.run(open('discord_token.txt').read())