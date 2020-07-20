import discord
import asyncio
import uuid
import re
import pygsheets
import json
import os
import random
from datetime import datetime, timedelta
from discord import File, User, Member, Embed
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

class Privilege(Enum):
	ADMIN = 0
	USER = 1

def check_cmd_ctx(cmd_ctx, privilege_level = Privilege.ADMIN):
	author = cmd_ctx.message.author
	if type(author) is not Member:
		raise Exception('PMs are not allowed.')

	if privilege_level == Privilege.ADMIN:
		if 'bot commander' not in map(lambda x: x.name.lower(), cmd_ctx.message.author.roles):
			raise BotErr('"Bot Commander" role required.')

def save():
	open('challenges.json', 'w').write(ctx.to_json())

def load():
	global ctx
	try:
		data = json.loads(open('challenges.json', 'r').read())
	except e:
		print(e)
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
		privilege_level = Privilege.USER
		user = cmd_ctx.message.author
		color = '#FFFFFF'
		
		if len(args) == 2:
			user = await UserConverter().convert(cmd_ctx, args[0])
			color = args[1]
			privilege_level = Privilege.ADMIN
		elif len(args) == 1:
			color = args[0]
		else:
			return await cmd_ctx.send('Invalid number of arguments({}). !set_color <user> color'.format(len(args)))

		check_cmd_ctx(cmd_ctx, privilege_level)
		if re.match(r'^#[a-fA-F0-9]{6}$', color) is None:
			return await cmd_ctx.send('Invalid color "{}".'.format(color))
		ctx.set_color(user, color)
		save()
		await cmd_ctx.send('Color has been changed.')
	except BotErr as e:
		await cmd_ctx.send(e)

@bot.command()
async def set_name(cmd_ctx, *args):
	try:
		if len(args) > 2:
			await cmd_ctx.send('Wrong nunber of arguments. !set_name <@user> name.')
			return

		privilege_level = Privilege.USER
		user = cmd_ctx.message.author
		name = ''

		if len(args) == 2:
			user = await UserConverter().convert(cmd_ctx, args[0])
			name = args[1]
			privilege_level = Privilege.ADMIN
		elif len(args) == 1:
			name = args[0]

		max_length = 32
		if len(name) > max_length:
			await cmd_ctx.send('Name is too long. Max is {} characters.'.format(max_length))
			return

		if len(name) != len([c for c in name if c.isalnum()]):
			await cmd_ctx.send('Error: Bad symbols in your name.')
			return

		check_cmd_ctx(cmd_ctx, privilege_level)
		ctx.set_name(user, name)
		save()
		await cmd_ctx.send('{} got "{}" as a new name.'.format(user.mention, name))
	except BotErr as e:
		await cmd_ctx.send(e)

@bot.command()
async def sync(cmd_ctx):
	check_cmd_ctx(cmd_ctx, Privilege.USER)
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
async def set_title(cmd_ctx, *args):
	if len(args) != 2:
		await cmd_ctx.send('Invalid number of arguments. Usage: !set_title <@user> <"title_name">')
		return

	check_cmd_ctx(cmd_ctx)
	user = await user_or_none(cmd_ctx, args[0])
	title_name = args[1]

	ctx.set_title(user, title_name)
	await cmd_ctx.send('Title "{}" has been assigned to {}'.format(title_name, user.mention))


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
		await cmd_ctx.send(e)

@bot.command()
async def rate(cmd_ctx, *args):
	try:
		user = cmd_ctx.message.author
		score = 0.0

		if len(args) < 1 or len(args) > 2:
			await cmd_ctx.send('Invalid number of arguments({}). !rate <@user> score'.format(len(args)))
			return

		privilege_level = Privilege.USER

		if len(args) > 1:
			privilege_level = Privilege.ADMIN
			user = await UserConverter().convert(cmd_ctx, args[0])
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
			user = await UserConverter().convert(cmd_ctx, args[0])

		if len(args) > 1:
			pool = args[1]

		check_cmd_ctx(cmd_ctx)
		title = ctx.reroll(user, pool)
		save()
		await cmd_ctx.send('User {} rolled "{}" from "{}" pool.'.format(user.mention, title, pool))
	except BotErr as e:
		await cmd_ctx.send(e)

@bot.command()
async def random_swap(cmd_ctx, *args):
	try:
		if len(args) < 2:
			await cmd_ctx.send('Wrong nunber of arguments. !random_swap @user @candidate1 <@candidate2...>')
			return

		if args[0] in args[1:]:
			await cmd_ctx.send("Can't swap titles between the same user.")
			return
		
		user = await UserConverter().convert(cmd_ctx, args[0])
		user2 = await UserConverter().convert(cmd_ctx, random.choice(args[1:]))

		check_cmd_ctx(cmd_ctx)
		title1, title2 = ctx.swap(user, user2)
		save()
		await cmd_ctx.send('User {} got "{}". User "{}" got {}.'.format(user.mention, title2, user2.mention, title1))
	except BotErr as e:
		await cmd_ctx.send(e)

@bot.command()
async def swap(cmd_ctx, *args):
	try:
		if len(args) != 2:
			await cmd_ctx.send('Wrong nunber of arguments. !swap @user1 @user2.')
			return

		if args[0] == args[1]:
			await cmd_ctx.send("Can't swap titles between the same user.")
			return
		user = await UserConverter().convert(cmd_ctx, args[0])
		user2 = await UserConverter().convert(cmd_ctx, args[1])

		check_cmd_ctx(cmd_ctx)
		title1, title2 = ctx.swap(user, user2)
		save()
		await cmd_ctx.send('User {} got "{}". User "{}" got {}.'.format(user.mention, title2, user2.mention, title1))
	except BotErr as e:
		await cmd_ctx.send(e)

@bot.command()
async def profile(cmd_ctx, *args):
	try:
		if len(args) > 1:
			await cmd_ctx.send('Wrong nunber of arguments. !profile <@user>')
			return

		user = cmd_ctx.message.author 

		if len(args) == 1:
			user = await UserConverter().convert(cmd_ctx, args[0])

		check_cmd_ctx(cmd_ctx, Privilege.USER)

		uname = ctx.get_name(user)
		avatar_url = str(user.avatar_url)

		ucolor = ctx.get_color(user)
		border_color = int('0x' + ucolor[1:],16)
		embedVar = Embed(title="", description='', color=border_color)
		embedVar.set_author(name=uname, icon_url=avatar_url)
		embedVar.set_thumbnail(url=avatar_url)

		challenges_num = ctx.get_challenges_num(user)
		if challenges_num > 0:
			completed_num = ctx.get_completed_num(user)
			embedVar.add_field(name="Challenges", value=str(challenges_num), inline=True)
			embedVar.add_field(name="Completed", value=str(completed_num), inline=True)

			avg_user_title_score = ctx.calc_avg_user_title_score(user)
			avg_score_user_gives = ctx.calc_avg_score_user_gives(user)

			embedVar.add_field(name="Avg. Score of Your Titles", value=f"{avg_user_title_score:.2f}", inline=False)
			embedVar.add_field(name="Avg. Score You Give", value=f"{avg_score_user_gives:.2f}", inline=True)

			most_watched_users = ctx.find_most_watched_users(user)
			most_showed_users = ctx.find_most_showed_users(user)

			if len(most_watched_users) > 0:
				length = max([len(i[0]) for i in most_watched_users]) + 2
				msg = '\n'.join([f'{i[0]:<{length}}{i[1]}' for i in most_watched_users])
				embedVar.add_field(name='Watched the most', value=msg, inline=False)

			if len(most_watched_users) > 0:
				length = max([len(i[0]) for i in most_showed_users]) + 2
				msg = '\n'.join([f'{i[0]:<{length}}{i[1]}' for i in most_showed_users])
				embedVar.add_field(name='Sniped the most', value=msg, inline=False)
		else:
			embedVar.add_field(name="No Challenges", value='Empty', inline=True)

		karma = ctx.calc_karma(user.id)
		embedVar.add_field(name="Karma", value=str(round(karma,2)), inline=False)

		karma_logo_url = 'https://i.imgur.com/wscUx1m.png'

		if karma > 200:
			karma_logo_url = 'https://i.imgur.com/oiypoFr.png'
		if karma > 300:
			karma_logo_url = 'https://i.imgur.com/4MOnqxX.png'
		if karma > 400:
			karma_logo_url = 'https://i.imgur.com/UJ8yOJ8.png'
		if karma > 500:
			karma_logo_url = 'https://i.imgur.com/YoGSX3q.png'
		if karma > 600:
			karma_logo_url = 'https://i.imgur.com/DeKg5P5.png'
		if karma > 700:
			karma_logo_url = 'https://i.imgur.com/byY9AfE.png'
		if karma > 800:
			karma_logo_url = 'https://i.imgur.com/XW4kc66.png'
		if karma > 900:
			karma_logo_url = 'https://i.imgur.com/3pPNCGV.png'

		embedVar.set_image(url=karma_logo_url)

		if ctx.is_in_challenge(user):
			time = ctx.get_end_round_time()
			embedVar.set_footer(text=f'Round ends on: {time}')

		await cmd_ctx.send(embed=embedVar)

	except BotErr as e:
		await cmd_ctx.send(e)

@bot.command()
async def karma(cmd_ctx, *args):
	try:
		if len(args) > 0:
			await cmd_ctx.send('Wrong nunber of arguments. !karma')
			return

		check_cmd_ctx(cmd_ctx, Privilege.USER)

		users = ctx.users.items()

		user_karma = []

		for user_id, user_info in users:
			karma = ctx.calc_karma(user_id)
			user_karma.append((karma, user_info.name))

		user_karma.sort()

		max_nickname_length = 0
		msg = ['```markdown']

		for i,uk in enumerate(user_karma[::-1]):
			max_nickname_length = max(max_nickname_length, len(uk[1]))

		max_nickname_length+=2
		for i,uk in enumerate(user_karma[::-1]):
			msg.append(f"{str(i+1)+')':<3} {uk[1]:<{max_nickname_length}}{uk[0]:.1f}")

		msg.append('```')

		msg = "\n".join(msg)
		await cmd_ctx.send(msg)

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
async def create_poll(cmd_ctx, *args):
	check_cmd_ctx(cmd_ctx)
	if len(args) > 1:
		return 

	if len(args) > 0:
		pool = args[0]

	titles = ctx.get_current_titles()

	for title in titles:
		msg = await cmd_ctx.send(title)
		await msg.add_reaction("👀")
	pass

@bot.command()
async def export(cmd_ctx, ext: str):
	check_cmd_ctx(cmd_ctx)
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

	gsheets_client = pygsheets.authorize('<client_secreet.json>')
	spreadsheet = gsheets_client.open_by_key('<sheets_key>')
	bot.loop.create_task(check_deadline())
	bot.run(open('discord_token.txt').read())