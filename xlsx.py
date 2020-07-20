import xlsxwriter
import re
from pygsheets.exceptions import WorksheetNotFound
from pygsheets.custom_types import HorizontalAlignment
from pygsheets import Cell, DataRange
from pygsheets.utils import format_addr

class DefaultWriter:
	def __init__(self, file_name):
		self.workbook = xlsxwriter.Workbook(file_name)
		self.worksheet = None

	def __del__(self):
		self.workbook.close()

	def new_worksheet(self, name):
		self.worksheet = self.workbook.add_worksheet(name)

	def set_col_width(self, col, width):
		self.worksheet.set_column(col, col, width)

	def write(self, row, col, string, format={}):
		self.worksheet.write(row, col, string, self.workbook.add_format(format))

	def write_url(self, row, col, url, string, format={}):
		self.worksheet.write_url(row, col, url, string=string, cell_format=self.workbook.add_format(format))

	def write_number(self, row, col, number, format={}):
		self.worksheet.write_number(row, col, number, self.workbook.add_format(format))

def col2tuple(col):
	try:
		rgb = list(map(lambda x: int(x, 16) / 255.0, re.findall(r'[a-fA-F0-9]{2}', col)))
		return (rgb[0], rgb[1], rgb[2], 0)
	except:
		raise Exception('Invalid color {}.'.format(col))
	
class GoogleSheetsWriter:
	def __init__(self, spreadsheet):
		self.spreadsheet = spreadsheet
		self.worksheet = None
		self.cells = []

	def finish_worksheet(self):
		if self.worksheet is None:
			return
		if len(self.cells) == 0:
			return

		max_col = 1
		for cell in self.cells:
			max_col = max(max_col, cell.col)

		DataRange((1, 1), (100, 26), self.worksheet).apply_format(Cell((1, 1)))

		self.worksheet.clear()
		self.worksheet.update_cells(self.cells)
		self.worksheet.adjust_column_width(1, self.worksheet.cols)
		self.worksheet = None
		self.cells = []

	def __del__(self):
		self.finish_worksheet()

	def new_cell(self, row, col, value, format={}):
		cell = Cell((row + 1, col + 1), value, self.worksheet)
		cell.unlink()
		if 'bold' in format and format['bold']:
			cell.set_text_format('bold', True)
		if 'align' in format and format['align'] == 'center':
			cell.horizontal_alignment = HorizontalAlignment.CENTER
		if 'bg_color' in format:
			cell.color = col2tuple(format['bg_color'])


		if 'font_strikeout' in format and format['font_strikeout']:
			cell.set_text_format('strikethrough', True)

		luminosity = (0.2126*cell.color[0] + 0.7152*cell.color[1] + 0.0722*cell.color[2])
		if luminosity >= 0.5:
			cell.set_text_format('foregroundColor', (0, 0, 0, 0))
		else:
			cell.set_text_format('foregroundColor', (1, 1, 1, 0))

		cell.set_text_format('underline', False)
		return cell

	def new_worksheet(self, name):
		self.finish_worksheet()
		try:
			self.worksheet = self.spreadsheet.worksheet_by_title(name)
		except WorksheetNotFound:
			self.worksheet = self.spreadsheet.add_worksheet(name)

	def set_col_width(self, col, width):
		pass

	def write(self, row, col, string, format={}):
		self.cells.append(self.new_cell(row, col, string, format))

	def write_url(self, row, col, url, string, format={}):
		cell = self.new_cell(row, col, '', format)
		cell.value = '=HYPERLINK("{}", "{}")'.format(url, string)
		self.cells.append(cell)

	def write_number(self, row, col, number, format={}):
		self.write(row, col, number, format)

def score_col(score):
	if score is None:
		return '#808080'
	elif score < 10.0 / 3.0:
		return '#DD7E6B'
	elif score < 10.0 / 1.5:
		return '#F1C232'
	else:
		return '#6AA84F'

class XlsxExporter:
	def __init__(self, writer, ctx):
		self.col = 0
		self.row = 0
		self.writer = writer
		self.ctx = ctx
		self.title_format = {
			'bold': True,
			'bg_color': '#C0C0C0',
			'align': 'center'
		}

		self.sorted_participants = None
		self.challenge = None
		self.max_col_width = 2

	def user_col(self, uid):
		return self.ctx.users[uid].color

	def write(self, string, format={}):
		self.max_col_width = max(self.max_col_width, len(string))
		self.writer.write(self.row, self.col, string, format)
		self.row += 1

	def write_url(self, url, string, format={}):
		if url is not None:
			self.max_col_width = max(self.max_col_width, len(string))
			self.writer.write_url(self.row, self.col, url, string, format)
			self.row += 1
		else:
			self.write(string, format)

	def write_number(self, number, format={}):
		self.max_col_width = max(self.max_col_width, len(str(number)))
		self.writer.write_number(self.row, self.col, number, format)
		self.row += 1

	def write_score(self, score):
		fmt = {
			'align': 'center',
			'bg_color': score_col(score)
		}
		if score is None:
			self.write('-', fmt)
		else:
			self.write_number(score, fmt)

	def next_col(self):
		self.writer.set_col_width(self.col, self.max_col_width)
		self.max_col_width = 2
		self.col += 1
		self.row = 0

	def export_pool(self, pool_name):
		self.write(pool_name + ' (unused titles)', self.title_format)
		for title in self.challenge.pools[pool_name].unused_titles:
			title_info = self.challenge.titles[title]
			self.write_url(title_info.url, title, {
				'bg_color': self.user_col(title_info.proposer),
			})

	def export_users(self):
		self.write('Participants', self.title_format)
		for uname, uid in self.sorted_participants:
			self.write(uname, { 'bg_color': self.user_col(uid) })

	def export_round(self, round_idx):
		rnd = self.challenge.rounds[round_idx]
		self.write('Round {} ({}-{})'.format(round_idx, rnd.short_begin(), rnd.short_end()), self.title_format)
		for _, uid in self.sorted_participants:
			failed = self.challenge.failed_participants
			if uid in failed and round_idx > failed[uid]:
				self.write('FAILED', {
					'bg_color': '#FF0000',
					'align': 'center'
				})
			else:
				title = rnd.rolls[uid].title
				title_info = self.challenge.titles[title]
				fmt = { 'bg_color': self.user_col(title_info.proposer) }
				if uid in failed and round_idx == failed[uid]:
					fmt = {
						'bg_color': '#FF0000',
						'font_strikeout': True
					}
				self.write_url(title_info.url, title, fmt)
		self.next_col()

		self.write('Score', self.title_format)
		for _, uid in self.sorted_participants:
			self.write_score(rnd.rolls[uid].score if uid in rnd.rolls else None)

	def export_stats(self):
		stats = []
		for _, uid in self.sorted_participants:
			min_ = None
			max_ = None
			sum_ = None
			n = 0
			for r in self.challenge.rounds:
				if uid not in r.rolls:
					continue
				score = r.rolls[uid].score
				if score is None:
					continue
				min_ = score if min_ is None else min(min_, score)
				max_ = score if max_ is None else max(max_, score)
				sum_ = score if sum_ is None else sum_ + score
				n += 1
			avg = None if sum_ is None else sum_ / n
			stats.append((min_, max_, avg))

		names = ['Min', 'Max', 'Avg']
		for i in range(len(names)):
			self.write(names[i], self.title_format)
			for s in stats:
				self.write_score(s[i])
			self.next_col()

	def export_challenge(self, challenge_name):
		self.writer.new_worksheet(challenge_name)

		self.challenge = self.ctx.challenges[challenge_name]
		self.col = 0
		self.row = 0
		self.max_col_width = 2
		self.sorted_participants = sorted([(self.ctx.users[uid].name, uid) for uid in self.challenge.participants], key=lambda x: x[0])

		self.export_users()
		self.next_col()

		for i in range(len(self.challenge.rounds)):
			self.export_round(i)
			self.next_col()

		self.export_stats()
		self.next_col()

		for pool in self.challenge.pools:
			self.export_pool(pool)
			self.next_col()
			self.next_col()

	def export(self):
		for challenge in self.ctx.challenges:
			self.export_challenge(challenge)
