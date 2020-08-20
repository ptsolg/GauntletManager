import json
import random
import xlsxwriter
import numpy as np
from datetime import datetime
from collections import Counter

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
    def __init__(self, title: str, score=None, progress = None):
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

    def sort(self):
        self.all_titles.sort()
        self.unused_titles.sort()

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
    def __init__(self, participants, failed_participants, titles, pools, rounds, channel_id, users_progress, idx):
        self.participants = participants
        self.failed_participants = failed_participants
        self.titles = titles
        self.pools = pools
        self.rounds = rounds
        self.channel_id = channel_id
        self.users_progress = users_progress
        self.idx = idx

    def pool(self, pool):
        if pool not in self.pools:
            raise BotErr(f'Cannot find "{pool}" pool.')
        return self.pools[pool]    

    def add_pool(self, name):
        if name in self.pools:
            raise BotErr(f'Pool "{name}" already exists.')
        self.pools[name] = Pool(all_titles=[], unused_titles=[])

    def add_title(self, pool, title_name, title_info):
        if title_name in self.titles:
            raise BotErr(f'Title "{title_name}" already exists.')
        self.pool(pool).add(title_name)
        self.pool(pool).sort()
        self.titles[title_name] = title_info
        
    def add_participant(self, user):
        if user.id in self.participants:
            raise BotErr(f'User {user.mention} is already participating in this challenge.')
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
        #return 
        if len(self.rounds) != 0:
            raise BotErr('Cannot add/delete user/title/pool after a challenge has started.')

    def check_participant(self, participant):
        if participant.id not in self.participants:
            raise BotErr(f'User {participant.mention} is not participating in this challenge.')
        if participant.id in self.failed_participants:
            raise BotErr(f'User {participant.mention} has failed this challenge.')

    def clear_progress(self):
        self.users_progress = { p: None for p in self.participants }

    def set_progress(self, user, progress):
        if user in self.users_progress:
            self.users_progress[user] = progress
        else:
            raise BotErr("Invalid User")

    def get_progress(self, user):
        if user in self.users_progress:
            return self.users_progress[user]
        else:
            raise BotErr("Invalid User")

    @classmethod
    def from_json(cls, data):
        participants = list(map(int, data['participants']))
        failed_participants = dict(map(lambda kv: (int(kv[0]), int(kv[1])), data['failed_participants'].items()))
        titles = dict(map(lambda kv: (kv[0], TitleInfo.from_json(kv[1])), data['titles'].items()))
        pools = dict(map(lambda kv: (kv[0], Pool.from_json(kv[1])), data['pools'].items()))
        rounds = list(map(Round.from_json, data['rounds']))
        if 'users_progress' in data:
            users_progress = dict(map(lambda kv: (int(kv[0]), kv[1]), data['users_progress'].items()))
        else:
            users_progress = { p: None for p in participants }
        idx = data['idx']

        return cls(participants, failed_participants, titles, pools, rounds, int(data['channel_id']), users_progress, idx)

class Context:
    def __init__(self, users, challenges, current_challenge=None):
        self.users = users
        self.challenges = challenges
        self.current_challenge = current_challenge

    def to_json(self):
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=1)

    @classmethod
    def from_json(cls, data):
        users = dict(map(lambda kv: (int(kv[0]), UserInfo.from_json(kv[1])), data['users'].items()))
        challenges = dict(map(lambda kv: (kv[0], Challenge.from_json(kv[1])), data['challenges'].items()))
        return cls(users, challenges, data['current_challenge'])

    def current(self):
        if self.current_challenge is None:
            raise BotErr('Create a new challenge first.')
        return self.challenges[self.current_challenge]  

    def get_current_titles(self):
        return self.current().titles

    def start_challenge(self, name, channel_id):
        if self.current_challenge is not None:
            raise BotErr(f'Finish "{self.current_challenge}" challenge first.')
        if name in self.challenges:
            raise BotErr(f'Challenge "{name}" already exists.')

        main = Pool(all_titles=[], unused_titles=[])
        self.challenges[name] = Challenge(
            participants=[],
            failed_participants={},
            titles={},
            pools={'main': main},
            rounds=[],
            channel_id=channel_id,
            users_progress={},
            idx=max([ i.idx for i in self.challenges.values() ]) + 1
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
            raise BotErr(f'Pool "{pool}" does not exist.')
        del challenge.pools[pool]

    def rename_pool(self, pool, new_name):
        challenge = self.current()
        challenge.check_not_started()
        if pool not in challenge.pools:
            raise BotErr(f'Pool "{pool}" does not exist.')
        challenge.pools[new_name] = challenge.pools[pool] 
        del challenge.pools[pool]

    def add_user(self, user):
        if user.id not in self.users:
            self.users[user.id] = UserInfo(user.name)
        challenge = self.current()
        challenge.check_not_started()
        challenge.add_participant(user)

    def remove_user(self, user):
        challenge = self.current()
        challenge.check_participant(user)

        if len(challenge.rounds) == 0:
            user_titles = [name for (name, info) in challenge.titles.items() if info.proposer == user.id ]
            for title in user_titles:
                self.remove_title(title)
            challenge.participants.remove(user.id)
        else:
            self.fail_user(user.id)            

    def set_color(self, user, color):
        if user.id not in self.users:
            raise BotErr('Invalid User')
        self.users[user.id] = UserInfo(self.users[user.id].name, color)

    def get_color(self, user):
        if user.id not in self.users:
            raise BotErr('Invalid User')
        return self.users[user.id].color

    def set_name(self, user, name):
        if user.id not in self.users:
            raise BotErr('Invalid User')
        self.users[user.id] = UserInfo(name, self.users[user.id].color)

    def get_name(self, user):
        if user.id not in self.users:
            raise BotErr('Invalid User')
        return self.users[user.id].name
            
    def get_challenges_num(self, user):
        return len([c for c in self.challenges.values() if user.id in c.participants])

    def get_completed_num(self, user):
        return len([c for c in self.challenges.values() if user.id in c.participants and user.id not in c.failed_participants and c != self.current()])

    def calc_karma(self, user_id):

        def calc_karma_diff_for_user(score):
            # scr = (score-5.0)
            # return ((-1 if scr < 0 else 0.5) * (scr)**2)/3
            return 5 + (score - 5 if score - 5 < 0 else (score - 5) * 0.25)

        def calc_karma_diff_for_titles(score):           
            # coef = 4.47213
            # return coef * (-1 if score-5 < 0 else 1)*(abs(score-5))**(0.5)
            return score

        def calc_avg_name(name):
            return sum([ord(x) for x in name])/len(name)

        max_karma = 1000
        current_karma = 0
        diff = 0

        for challenge in sorted(self.challenges.values(), key=lambda x: x.idx):
            diff = 0
            for r in challenge.rounds:
                if not r.is_finished:
                    continue
                
                new_karma = current_karma
                for participant, entry in r.rolls.items():
                    title = entry.title
                    score = entry.score
                    karma_step = 2
                    karma_weights = [0.5, 0.50]
                    karma_diffs = []

                    if score and challenge.titles[title].proposer == user_id and participant != user_id:
                        karma_diffs.append(calc_karma_diff_for_titles(score))

                    if score and participant == user_id and challenge.titles[title].proposer != user_id:
                        karma_diffs.append(calc_karma_diff_for_user(score))

                    for i in range(len(karma_diffs)):
                        # if calc_avg_name(self.users[participant].name) < calc_avg_name(title):
                        #     karma_diffs[i] *= 0.971 
                        # else:
                        #     karma_diffs[i] *= 1.029
                        new_karma += karma_weights[i] * karma_diffs[i] * karma_step
                    if type(new_karma) == complex:
                        new_karma = new_karma.real
                    new_karma = min(new_karma, max_karma)
                    new_karma = max(new_karma, 0)        

                diff = new_karma - current_karma
                current_karma = new_karma

        return current_karma, diff

    def calc_avg_user_title_score(self, user):
        scores=[]
        for challenge in self.challenges.values():
            for r in challenge.rounds:
                if not r.is_finished:
                    continue

                for entry in r.rolls.values():
                    title = entry.title
                    score = entry.score
                    if score and challenge.titles[title].proposer == user.id:
                        scores.append(score)
        
        return sum(scores) / len(scores)

    def calc_avg_score_user_gives(self, user):
        scores=[]
        for challenge in self.challenges.values():
            for r in challenge.rounds:
                if not r.is_finished:
                    continue

                for user_id, entry in r.rolls.items():
                    score = entry.score
                    if score and user_id == user.id:
                        scores.append(score)

        return sum(scores) / len(scores)

    def find_most_watched_users(self, user):
        watched = Counter()
        for challenge in self.challenges.values():
            for r in challenge.rounds:
                if not r.is_finished:
                    continue

                for user_id, entry in r.rolls.items():
                    title = entry.title
                    proposer = challenge.titles[title].proposer
                    if user_id == user.id:
                        watched[self.users[proposer].name] += 1

        return [(i[0], i[1]) for i in watched.most_common(None) if i[1] == watched.most_common(1)[0][1]]

    def find_most_showed_users(self, user):
        showed = Counter()
        for challenge in self.challenges.values():
            for r in challenge.rounds:
                if not r.is_finished:
                    continue

                for user_id, entry in r.rolls.items():
                    title = entry.title
                    proposer = challenge.titles[title].proposer
                    if proposer == user.id:
                        showed[self.users[user_id].name] += 1

        return [(i[0], i[1]) for i in showed.most_common(None) if i[1] == showed.most_common(1)[0][1]]

    def add_title(self, pool, proposer, title_name, title_url):
        challenge = self.current()
        challenge.check_participant(proposer)
        challenge.add_title(pool, title_name, TitleInfo(proposer.id, title_url))

    def remove_title(self, title_name):
        challenge = self.current()

        if title_name not in challenge.titles:
            raise BotErr(f'Title "{title_name}" does not exist.')

        del challenge.titles[title_name]
        for (_, pool) in challenge.pools.items():
            if title_name in pool.all_titles:
                pool.all_titles.remove(title_name)
            if title_name in pool.unused_titles:
                pool.unused_titles.remove(title_name)

    def rename_title(self, old_title, new_title):
        challenge = self.current()

        if old_title not in challenge.titles:
            raise BotErr(f'Title "{old_title}" does not exist.')

        challenge.titles[new_title] = challenge.titles[old_title]
        del challenge.titles[old_title]
        for (_, pool) in challenge.pools.items():
            if old_title in pool.all_titles:
                pool.all_titles[pool.all_titles.index(old_title)] = new_title
            if old_title in pool.unused_titles:
                pool.unused_titles[pool.unused_titles.index(old_title)] = new_title

    def clear_progress(self):
        self.current().clear_progress()
    
    def set_progress(self, user, progress):
        if user.id in self.current().participants:
            self.current().set_progress(user.id, progress)
        else:
            raise BotErr('Invalid User')

    def get_progress(self, user):
        if user.id in self.current().participants:
            return self.current().get_progress(user.id)
        else:
            raise BotErr('Invalid User')
    
    def get_all_progress(self):
        users_progress = self.current().users_progress
        rolls = self.current().last_round().rolls
        ans = {}
        for participant, progress in users_progress.items():
            score = rolls[participant].score
            if score:
                progress = f'Done: {score}' 
            ans[self.users[participant].name] = progress

        return ans

    def start_round(self, timedelta, pool_name):
        challenge = self.current()
        pool = challenge.pools[pool_name]

        if len(challenge.rounds) != 0 and not challenge.rounds[-1].is_finished:
            raise BotErr(f'Finish round {len(challenge.rounds)} first.')

        participants = []
        for p in challenge.participants:
            if p not in challenge.failed_participants:
                participants.append(p)
        if len(participants) == 0:
            raise BotErr('Not enough participants to start a round.')

        #random.shuffle(participants)
        titles = pool.pop_n(len(participants))
        rolls = dict(zip(participants, map(RollInfo, titles)))
        begin = datetime.now()
        end = begin + timedelta
        challenge.rounds.append(Round(rolls, begin.strftime(Round.TIME_FMT), end.strftime(Round.TIME_FMT), is_finished=False))

        self.clear_progress()

        return dict(zip([ self.users[p].name for p in participants], map(RollInfo, titles)))

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

    def fail_user(self, user):
        challenge = self.current()
        rnd = challenge.last_round()
        rnd_no = len(challenge.rounds) - 1

        failed = challenge.failed_participants
        if user not in failed:
            failed[user] = rnd_no
            rnd.rolls[user].score = None

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
                pool.sort()
                break
            
        return new_title

    def set_title(self, user, title):
        challenge = self.current()
        last_round = challenge.last_round()
        challenge.check_participant(user)

        old_title = last_round.rolls[user.id].title

        last_round.rolls[user.id].title = title
        for _, pool in challenge.pools.items():
            if title in pool.all_titles:
                pool.unused_titles.remove(title)
                pool.sort()
                break

        for _, pool in challenge.pools.items():
            if old_title in pool.all_titles:
                pool.unused_titles.append(old_title)
                pool.sort()
                break

    def swap(self, user1, user2):
        challenge = self.current()
        last_round = challenge.last_round()
        
        challenge.check_participant(user1)
        challenge.check_participant(user2)

        title1 = last_round.rolls[user1.id].title
        title2 = last_round.rolls[user2.id].title

        last_round.rolls[user1.id].title = title2
        last_round.rolls[user2.id].title = title1
        return title1, title2

    def is_in_challenge(self, user):
        return user.id in self.current().participants

    def get_end_round_time(self): 
        try:
            return self.current().last_round().parse_end()
        except BotErr as e:
            return None