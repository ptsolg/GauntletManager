import json
import random
import xlsxwriter
from datetime import datetime

class BotErr(Exception):
	def __init__(self, msg):
		self.msg = msg

	def __str__(self):
		return self.msg

class UserInfo:
	def __init__(self, name, color='#FFFFFF'):
		self.name = name
		self.color = color

	@classmethod
	def from_json(cls, data):
		return cls(**data)

class TitleInfo:
	def __init__(self, proposer, url):
		self.proposer = proposer
		self.url = url

	@classmethod
	def from_json(cls, data):
		return cls(**data)

class RollInfo:
	def __init__(self, title: str, score=None):
		self.title = title
		self.score = score

	@classmethod
	def from_json(cls, data):
		return cls(data['title'], data['score'])

class Round:
	TIME_FMT = '%H:%M %d.%m.%y'
	SHORT_TIME_FMT = '%d.%m'

	def __init__(self, rolls, begin: str, end: str, is_finished: bool):
		self.begin = begin
		self.end = end
		self.rolls = rolls
		self.is_finished = is_finished

	def parse_begin(self):
		return datetime.strptime(self.begin, Round.TIME_FMT)

	def parse_end(self):
		return datetime.strptime(self.end, Round.TIME_FMT)

	def short_begin(self):
		return self.parse_begin().strftime(Round.SHORT_TIME_FMT)

	def short_end(self):
		return self.parse_end().strftime(Round.SHORT_TIME_FMT)

	def check_deadline(self):
		if datetime.now() > self.parse_end():
			raise BotErr('Round has ended.')

	@classmethod
	def from_json(cls, data):
		rolls = dict(map(lambda kv: (int(kv[0]), RollInfo.from_json(kv[1])), data['rolls'].items()))
		return cls(rolls, data['begin'], data['end'], bool(data['is_finished']))

class Pool:
	def __init__(self, all_titles, unused_titles):
		self.all_titles = all_titles
		self.unused_titles = unused_titles

	def check_size(self, n):
		if n > len(self.unused_titles):
			raise BotErr('Not enough titles in pool.')

	def add(self, title: str):
		self.all_titles.append(title)
		self.unused_titles.append(title)

	def pop(self):
		self.check_size(1)
		return self.unused_titles.pop(random.randrange(len(self.unused_titles)))

	def pop_n(self, n):
		self.check_size(n)
		return [self.pop() for _ in range(n)]

	@classmethod
	def from_json(cls, data):
		return cls(data['all_titles'], data['unused_titles'])

class Challenge:
	def __init__(self, participants, failed_participants, titles, pools, rounds, channel_id):
		self.participants = participants
		self.failed_participants = failed_participants
		self.titles = titles
		self.pools = pools
		self.rounds = rounds
		self.channel_id = channel_id

	def pool(self, pool):
		if pool not in self.pools:
			raise BotErr('Cannot find "{}" pool.'.format(pool))
		return self.pools[pool]	

	def add_pool(self, name):
		if name in self.pools:
			raise BotErr('Pool "{}" already exists.'.format(name))
		self.pools[name] = Pool(all_titles=[], unused_titles=[])

	def add_title(self, pool, title_name, title_info):
		if title_name in self.titles:
			raise BotErr('Title "{}" already exists.'.format(title_name))
		self.pool(pool).add(title_name)
		self.titles[title_name] = title_info
		
	def add_participant(self, user):
		if user.id in self.participants:
			raise BotErr('User {} is already participating in this challenge.'.format(user.mention))
		self.participants.append(user.id)

	def last_round(self):
		l = len(self.rounds)
		if l == 0:
			raise BotErr('Create a new round first.')
		rnd = self.rounds[l - 1]
		if rnd.is_finished:
			raise BotErr('The round has ended.')
		return rnd

	def check_not_started(self):
		if len(self.rounds) != 0:
			raise BotErr('Cannot add/delete user/title/pool after a challenge has started.')

	def check_participant(self, participant):
		if participant.id not in self.participants:
			raise BotErr('User {} is not participating in this challenge.'.format(participant.mention))
		if participant.id in self.failed_participants:
			raise BotErr('User {} has failed this challenge.'.format(participant.mention))

	@classmethod
	def from_json(cls, data):
		participants = list(map(int, data['participants']))
		failed_participants = dict(map(lambda kv: (int(kv[0]), int(kv[1])), data['failed_participants'].items()))
		titles = dict(map(lambda kv: (kv[0], TitleInfo.from_json(kv[1])), data['titles'].items()))
		pools = dict(map(lambda kv: (kv[0], Pool.from_json(kv[1])), data['pools'].items()))
		rounds = list(map(Round.from_json, data['rounds']))
		return cls(participants, failed_participants, titles, pools, rounds, int(data['channel_id']))

class Context:
	def __init__(self, users, challenges, current_challenge=None):
		self.users = users
		self.challenges = challenges
		self.current_challenge = current_challenge

	def to_json(self):
		return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=4)

	@classmethod
	def from_json(cls, data):
		users = dict(map(lambda kv: (int(kv[0]), UserInfo.from_json(kv[1])), data['users'].items()))
		challenges = dict(map(lambda kv: (kv[0], Challenge.from_json(kv[1])), data['challenges'].items()))
		return cls(users, challenges, data['current_challenge'])

	def current(self):
		if self.current_challenge is None:
			raise BotErr('Create a new challenge first.')
		return self.challenges[self.current_challenge]	

	def start_challenge(self, name, channel_id):
		if self.current_challenge is not None:
			raise BotErr('Finish "{}" challenge first.'.format(self.current_challenge))
		if name in self.challenges:
			raise BotErr('Challenge "{}" already exists.'.format(name))

		main = Pool(all_titles=[], unused_titles=[])
		self.challenges[name] = Challenge(
			participants=[],
			failed_participants={},
			titles={},
			pools={'main': main},
			rounds=[],
			channel_id=channel_id
		)
		self.current_challenge = name

	def end_challenge(self):
		rounds = self.current().rounds
		if len(rounds) != 0:
			if not rounds[-1].is_finished:
				self.end_round()
		self.current_challenge = None

	def add_pool(self, name):
		challenge = self.current()
		challenge.check_not_started()
		challenge.add_pool(name)

	def remove_pool(self, pool):
		challenge = self.current()
		challenge.check_not_started()
		if pool not in challenge.pools:
			raise BotErr('Pool "{}" does not exist.'.format(pool))
		del challenge.pools[pool]

	def add_user(self, user):
		if user.id not in self.users:
			self.users[user.id] = UserInfo(user.name)
		challenge = self.current()
		challenge.check_not_started()
		challenge.add_participant(user)

	def remove_user(self, user):
		challenge = self.current()
		challenge.check_not_started()
		challenge.check_participant(user)

		user_titles = [name for (name, info) in challenge.titles.items() if info.proposer == user.id ]
		for title in user_titles:
			self.remove_title(title)
		challenge.participants.remove(user.id)

	def set_color(self, user, color):
		self.users[user.id] = UserInfo(user.name, color)

	def add_title(self, pool, proposer, title_name, title_url):
		challenge = self.current()
		challenge.check_not_started()
		challenge.check_participant(proposer)
		challenge.add_title(pool, title_name, TitleInfo(proposer.id, title_url))

	def remove_title(self, title_name):
		challenge = self.current()
		challenge.check_not_started()

		if title_name not in challenge.titles:
			raise BotErr('Title "{}" does not exist.'.format(title_name))

		del challenge.titles[title_name]
		for (_, pool) in challenge.pools.items():
			if title_name in pool.all_titles:
				pool.all_titles.remove(title_name)
			if title_name in pool.unused_titles:
				pool.unused_titles.remove(title_name)

	def start_round(self, timedelta):
		challenge = self.current()
		main = challenge.pools['main']

		if len(challenge.rounds) != 0 and not challenge.rounds[-1].is_finished:
			raise BotErr('Finish round {} first.'.format(len(challenge.rounds)))

		participants = []
		for p in challenge.participants:
			if p not in challenge.failed_participants:
				participants.append(p)
		if len(participants) == 0:
			raise BotErr('Not enough participants to start a round.')

		titles = main.pop_n(len(participants))
		rolls = dict(zip(participants, map(RollInfo, titles)))
		begin = datetime.now()
		end = begin + timedelta
		challenge.rounds.append(Round(rolls, begin.strftime(Round.TIME_FMT), end.strftime(Round.TIME_FMT), is_finished=False))

	def end_round(self):
		challenge = self.current()
		rnd = challenge.last_round()
		rnd_no = len(challenge.rounds) - 1

		for participant, roll in rnd.rolls.items():
			failed = challenge.failed_participants
			if roll.score is None and participant not in failed:
				failed[participant] = rnd_no

		rnd.end = datetime.now().strftime(Round.TIME_FMT)
		rnd.is_finished = True

	def extend_round(self, timedelta):
		challenge = self.current()
		last_round = challenge.last_round()
		last_round.check_deadline()
		last_round.end = (last_round.parse_end() + timedelta).strftime(Round.TIME_FMT)

	def rate(self, user, score):
		challenge = self.current()
		challenge.check_participant(user)
		last_round = challenge.last_round()
		last_round.check_deadline()
		last_round.rolls[user.id].score = score

	def reroll(self, user, pool_name):
		challenge = self.current()
		challenge.check_participant(user)
		last_round = challenge.last_round()
		last_round.check_deadline()

		old_title = last_round.rolls[user.id].title
		new_title = challenge.pool(pool_name).pop()
		last_round.rolls[user.id].title = new_title

		for _, pool in challenge.pools.items():
			if old_title in pool.all_titles:
				pool.unused_titles.append(old_title)
				break

		return new_title