import sqlite3
from sqlite3 import Error
import os
import json
from datetime import datetime
import challenge

db_file = 'challenges.db'
ctx = challenge.Context.from_json(json.loads(open('challenges.json', 'r').read()))
efusarts_guild = 732568984846598215
time_fmt = '%H:%M %d.%m.%y'
db = None

if os.path.isfile(db_file):
    os.remove(db_file)

def guild_id(discord_id):
    (id,) = db.execute('SELECT id FROM guild WHERE discord_id = ?', [discord_id]).fetchone()
    return id

def user_id(discord_id):
    (id,) = db.execute('SELECT id FROM user WHERE discord_id = ?', [discord_id]).fetchone()
    return id

def participant_id(discord_id, challenge_id):
    (id,) = db.execute('''
		SELECT P.id FROM user U
		JOIN participant P ON P.user_id = U.id
		WHERE U.discord_id = ? AND P.challenge_id = ?''', [discord_id, challenge_id]).fetchone()
    return id

def challenge_id(name):
    (id,) = db.execute('SELECT id FROM challenge WHERE name = ?', [name]).fetchone()
    return id

def pool_id(challenge_id, name):
    (id,) = db.execute('SELECT id FROM pool WHERE challenge_id = ? AND name = ?', [challenge_id, name]).fetchone()
    return id

def title_id(challenge_id, name):
    (id,) = db.execute('''
        SELECT T.id FROM title T
        JOIN pool P ON P.id = T.pool_id
        WHERE P.challenge_id = ? AND T.name = ?''', [challenge_id, name]).fetchone()
    return id

def round_id(challenge_id, num):
    (id,) = db.execute('SELECT id FROM round WHERE challenge_id = ? AND num = ?', [challenge_id, num]).fetchone()
    return id

def init_guild():
    db.execute('INSERT INTO guild (discord_id) VALUES (?)', [efusarts_guild])

def init_user():
    for discord_id, user in ctx.users.items():
        db.execute('INSERT INTO user (discord_id, color, name, karma) VALUES (?, ?, ?, ?)',
            [discord_id, user.color, user.name, ctx.calc_karma(discord_id)[0]])

def init_challenge(name, challenge):
    rounds = challenge.rounds
    assert len(rounds) != 0
    start_time = datetime.strptime(rounds[0].begin, time_fmt)
    finish_time = datetime.strptime(rounds[-1].end, time_fmt)
    db.execute('INSERT INTO challenge (guild_id, name, start_time, finish_time) VALUES (?, ?, ?, ?)',
        [guild_id(efusarts_guild), name, start_time, finish_time])

def init_current_challenge():
	db.execute('UPDATE guild SET current_challenge_id = ? WHERE id = ?',
		[challenge_id(ctx.current_challenge), guild_id(efusarts_guild)])

def init_participant(cid, challenge):
    for discord_id in challenge.participants:
        db.execute('INSERT INTO participant (challenge_id, user_id) VALUES (?, ?)', [cid, user_id(discord_id)])

def init_pool(cid, name):
    db.execute('INSERT INTO pool (challenge_id, name) VALUES (?, ?)', [cid, name])

def init_title(cid, pool_id, challenge, pool):
    for name in pool.all_titles:
        title = challenge.titles[name]
        is_used = not (name in pool.unused_titles)
        db.execute('INSERT INTO title (pool_id, participant_id, name, url, is_used) VALUES (?, ?, ?, ?, ?)',
            [pool_id, participant_id(title.proposer, cid), name, title.url, is_used])

def init_round(cid, num, round):
    start_time = datetime.strptime(round.begin, time_fmt)
    finish_time = datetime.strptime(round.end, time_fmt)
    db.execute('INSERT INTO round (num, challenge_id, start_time, finish_time, is_finished) VALUES (?, ?, ?, ?, ?)',
        [num, cid, start_time, finish_time, round.is_finished])

def init_roll(cid, challenge, round_num, rolls):
    for discord_id, roll in rolls.items():
        db.execute('INSERT INTO roll (round_id, participant_id, title_id, score) VALUES (?, ?, ?, ?)',
            [round_id(cid, round_num), participant_id(discord_id, cid), title_id(cid, roll.title), roll.score])

def init_failed_participant(cid, challenge):
    for discord_id, round_num in challenge.failed_participants.items():
        db.execute('UPDATE participant SET failed_round_id = ? WHERE id = ?',
            [round_id(cid, round_num), participant_id(discord_id, cid)])

try:
    db = sqlite3.connect(db_file)
    db.executescript(open('../init.sql', 'r').read())
    init_guild()
    init_user()
    for challenge_name, challenge in ctx.challenges.items():
        if len(challenge.rounds) == 0:
            continue
        init_challenge(challenge_name, challenge)
        cid = challenge_id(challenge_name)
        init_participant(cid, challenge)
        for pool_name, pool in challenge.pools.items():
            init_pool(cid, pool_name)
            init_title(cid, pool_id(cid, pool_name), challenge, pool)
        for num, round in enumerate(challenge.rounds):
            init_round(cid, num, round)
            init_roll(cid, challenge, num, round.rolls)
        init_failed_participant(cid, challenge)
    #init_current_challenge()
    db.commit()
    db.close()
except Error as e:
    print(e)
