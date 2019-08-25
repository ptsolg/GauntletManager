import unittest
import random
from datetime import timedelta
from challenge import Context, BotErr

class User:
	def __init__(self, name: str):
		self.mention = '@' + name
		self.id = random.randint(0, 2**64)
		self.name = name

def create_challenge(name):
	ctx = Context({}, {})
	ctx.new_challenge(name=name, channel_id=123)
	return ctx

class TestCommands(unittest.TestCase):
	def test_new_challenge(self):
		ctx = create_challenge('test')
		self.assertEqual(ctx.current_challenge, 'test')
		self.assertTrue('main' in ctx.current().pools)

	def test_challenge_exists(self):
		ctx = create_challenge('test')
		ctx.current_challenge = None # todo: replace later with ctx.end_challenge() or smth
		with self.assertRaises(BotErr) as e:
			ctx.new_challenge('test', 123)
		self.assertEqual(str(e.exception), 'Challenge "test" already exists.')

	def test_finish_prev_challenge_first(self):
		ctx = create_challenge('test')
		with self.assertRaises(BotErr) as e:
			ctx.new_challenge('test123', 123)
		self.assertEqual(str(e.exception), 'Finish "test" challenge first.')		

	def test_new_pool(self):
		ctx = create_challenge('test')
		ctx.new_pool('trash')
		self.assertTrue('trash' in ctx.current().pools)

	def test_pool_exists(self):
		ctx = create_challenge('test')
		with self.assertRaises(BotErr) as e:
			ctx.new_pool('main')
		self.assertEqual(str(e.exception), 'Pool "main" already exists.')

	def test_add_user(self):
		ctx = create_challenge('test')
		user = User('user')
		ctx.add_user(user)
		self.assertTrue(user.id in ctx.users)
		self.assertTrue(user.id in ctx.current().participants)

	def test_user_exists(self):
		ctx = create_challenge('test')
		user = User('user')
		ctx.add_user(user)
		with self.assertRaises(BotErr) as e:
			ctx.add_user(user)
		self.assertEqual(str(e.exception), 'User @user is already participating in this challenge.')

	def test_add_title(self):
		ctx = create_challenge('test')
		user = User('user')
		ctx.add_user(user)
		ctx.add_title('main', user, 'title', 'url')
		challenge = ctx.current()
		self.assertTrue('title' in challenge.titles)
		self.assertTrue('title' in challenge.pools['main'].all_titles)
		self.assertTrue('title' in challenge.pools['main'].unused_titles)

	def test_add_title_errors(self):
		ctx = create_challenge('test')

		with self.assertRaises(BotErr) as e:
			ctx.add_title('main', User('user'), 'title', 'url')
		self.assertEqual(str(e.exception), 'User @user is not participating in this challenge.')

		user = User('user')
		ctx.add_user(user)

		with self.assertRaises(BotErr) as e:
			ctx.add_title('trash', user, 'title', 'url')
		self.assertEqual(str(e.exception), 'Cannot find "trash" pool.')

	def test_start_round(self):
		ctx = create_challenge('test')
		users = [User('user_' + str(i)) for i in range(0, 10)]
		for u in users:
			ctx.add_user(u)
			ctx.add_title('main', u, u.name + '_title', 'url')
		ctx.start_round(timedelta(days=1))

		self.assertEqual(len(ctx.current().pools['main'].unused_titles), 0)
		rnd = ctx.current().last_round()
		self.assertEqual(len(rnd.rolls), 10)
		for u in users:
			self.assertTrue(u.id in rnd.rolls)

	def test_start_round_errors(self):
		ctx = create_challenge('test')
		user = User('user')
		ctx.add_user(user)

		with self.assertRaises(BotErr) as e:
			ctx.start_round(timedelta(days=1))
		self.assertEqual(str(e.exception), 'Not enough titles in pool.')


		ctx.add_title('main', user, 'title1', 'url')
		ctx.add_title('main', user, 'title2', 'url')
		ctx.start_round(timedelta(days=1))

		with self.assertRaises(BotErr) as e:
			ctx.start_round(timedelta(days=1))
		self.assertEqual(str(e.exception), 'Finish round 1 first.')

		ctx.end_round()
		with self.assertRaises(BotErr) as e:
			ctx.start_round(timedelta(days=1))
		self.assertEqual(str(e.exception), 'Not enough participants to start a round.')

	def test_rate(self):
		ctx = create_challenge('test')
		users = [User('user_' + str(i)) for i in range(0, 10)]
		for u in users:
			ctx.add_user(u)
			ctx.add_title('main', u, u.name + '_title', 'url')
		ctx.start_round(timedelta(days=1))

		for u in users:
			ctx.rate(u, 10)
			self.assertEqual(ctx.current().last_round().rolls[u.id].score, 10)

	def test_reroll(self):
		ctx = create_challenge('test')
		ctx.new_pool('trash')
		u = User('user')
		ctx.add_user(u)
		ctx.add_title('main', u, '11', '11')
		ctx.add_title('trash', u, '22', '22')
		ctx.start_round(timedelta(days=1))
		ctx.reroll(u, 'trash')

		challenge = ctx.current()
		self.assertTrue('11' in challenge.pools['main'].unused_titles)
		self.assertEqual(len(challenge.pools['trash'].unused_titles), 0)

	def test_reroll_errors(self):
		ctx = create_challenge('test')
		u = User('user')
		ctx.add_user(u)
		ctx.add_title('main', u, '11', '11')
		ctx.new_pool('trash')
		ctx.start_round(timedelta(days=1))
		
		with self.assertRaises(BotErr) as e:
			ctx.reroll(u, 'trash')
		self.assertEqual(str(e.exception), 'Not enough titles in pool.')

		with self.assertRaises(BotErr) as e:
			ctx.reroll(User('abc'), 'trash')
		self.assertEqual(str(e.exception), 'User @abc is not participating in this challenge.')		

	def test_end_round(self):
		ctx = create_challenge('test')
		users = [User('user_' + str(i)) for i in range(0, 10)]
		for u in users:
			ctx.add_user(u)
			ctx.add_title('main', u, u.name + '_title', 'url')
		ctx.start_round(timedelta(days=1))
		for i in range(5):
			ctx.rate(users[i], 1)
		ctx.end_round()

		for i in range(5, 10):
			self.assertEqual(ctx.current().failed_participants[users[i].id], 0)
		self.assertTrue(ctx.current().rounds[0].is_finished)

	def test_remove(self):
		ctx = create_challenge('test')
		challenge = ctx.current()
		u = User('user')
		ctx.add_user(u)
		ctx.new_pool('trash')

		ctx.add_title('main', u, '11', '11')
		ctx.add_title('trash', u, '22', '22')

		ctx.remove_title('22')
		self.assertTrue('22' not in challenge.pools['trash'].all_titles)
		self.assertTrue('22' not in challenge.pools['trash'].unused_titles)
		self.assertTrue('22' not in challenge.titles)

		ctx.remove_user(u)
		self.assertTrue('11' not in challenge.pools['main'].all_titles)
		self.assertTrue('11' not in challenge.pools['main'].unused_titles)
		self.assertTrue('11' not in challenge.titles)
		self.assertTrue(u.id not in challenge.participants)

		ctx.remove_pool('trash')
		self.assertTrue('trash' not in challenge.pools)

if __name__ == '__main__':
	unittest.main()