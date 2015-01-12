# encoding: utf-8

# RPG-CLUB Market Analyzer 1.2.0

# Changelog:
# 1.2.0 - show all dupe offers for each item, not only best
# 1.1.0 - add printing dupe chain
# 1.0.1 - fix dupe analyze logic
# 1.0.0 - initial release


import re
import datetime
import collections
import urllib.error
import urllib.request

#print_encoding = 'utf-8'
print_encoding = 'windows-1251'


_rtag = re.compile(r'</?\w+[^>]*>*')
_rrows = re.compile(r'<tr[^>]*>\s*(?:<td[^>]*>.*?</td>\s*){8}', flags=re.IGNORECASE)
_ritems = re.compile(r'<td[^>]*>\s*(.*?)\s*</td>', flags=re.IGNORECASE)


def print_dupe():
	dupes = []

	offers = collections.defaultdict(list)
	for o in download_actual_offers():
		offers[o.item_name].append(o)
		offers[o.item_name].sort(key=lambda x: (x.cost, -x.count))  # cost asc, count desc

	for d in download_actual_demands():
		item_offers = offers.get(d.item_name)

		if not item_offers:
			continue

		dupe_offers = [o for o in item_offers if o.cost < d.cost]

		if dupe_offers:
			dupes.append((d, dupe_offers))

	if not dupes:
		print("Sorry, dupe not found")
	else:
		print("Great! Dupe was found!")
		for demand, offers in dupes:
			offer = next((o for o in offers if o.count), None)
			if offer is None:
				continue

			buy_count = min(demand.count,  offer.count)

			if not buy_count:
				continue

			offer.count -= buy_count
			demand.count -= buy_count

			equity = buy_count * (demand.cost - offer.cost)

			print(
				'''Dupe '{item_name}', equity {equity} aden, required {total_price} aden:\n'''
				'''\tbuy {count} from "{seller_name}" ({seller_city}),\n'''
				'''\tsell to "{buyer_name}" ({buyer_city})'''.format(
					item_name=offer.item_name,
					equity=equity,
					total_price=buy_count * offer.cost,
					count=buy_count,
					seller_name=offer.owner_name,
					seller_city=offer.city,
					buyer_name=demand.owner_name,
					buyer_city=demand.city,
				),
				end='\n\n'
			)


def tag_split(txt):
	return [x for x in _rtag.split(txt) if x]


class Trade:
	def __init__(self, create_date, owner_name, city, item_name, count, cost, packet=False):
		self.create_date = create_date
		self.owner_name = owner_name
		self.city = city
		self.item_name = item_name
		self.count = int(count)
		self.cost = int(cost)
		self.packet = packet

	def __repr__(self):
		return 'Owner: {}, Item: {}, Count: {}, Cost: {}'.format(
			self.owner_name,
			self.item_name,
			self.count,
			self.cost
		)

	@staticmethod
	def _extract_date(
		txt,
		_rdate=re.compile(r'\d+/\d+/\d+ \d+:\d+:\d+\s*\w{2}', flags=re.IGNORECASE)
	):
		mo = _rdate.search(txt)
		if mo:
			return datetime.datetime.strptime(mo.group(0), '%m/%d/%Y %H:%M:%S %p')

		return None

	@classmethod
	def from_table_row(cls, row):
		create_date, owner_city, _, item_name_ru_en, _, count, _, cost = _ritems.findall(row)

		create_date = cls._extract_date(create_date)

		owner_name, city = tag_split(owner_city)
		owner_name = owner_name.strip()

		packet = '*' in cost

		cost = cost.replace('.', '')
		cost = cost.strip(' *')

		name_parts = tag_split(item_name_ru_en)
		try:
			if len(name_parts) > 2:
				# example:  ['Baby Kookaburra Ocarina', 'Окарина Детеныша Кукабарры', '+63']
				item_name_en, item_name_ru, mod = name_parts
				item_name_en += ' %s' % mod
				item_name_ru += ' %s' % mod
			elif len(name_parts) > 1:
				item_name_en, item_name_ru = name_parts
			else:
				item_name_en = item_name_ru = name_parts[0]
		except ValueError:
			print(item_name_ru_en)
			raise

		return cls(create_date, owner_name, city, item_name_en, count, cost, packet)


def download_actual_demands():
	print("Download demands... ", end='', flush=True)
	page = _read_page('http://market.bot.rpg-club.com/motherland/buy/price/desc')
	res = _load_trades(page)
	print("Done!")
	return res


def download_actual_offers():
	print("Download offers... ", end='', flush=True)
	page = _read_page('http://market.bot.rpg-club.com/motherland/sell/price/asc')
	res = _load_trades(page)
	print("Done!")
	return res


def _read_page(addr, retry=3):
	while True:
		try:
			resp = urllib.request.urlopen(addr)
		except urllib.error.HTTPError as exc:
			print("Error, retry %s: %r" % (retry, exc))

			retry -= 1
			if not retry:
				raise

		break

	charset = resp.headers.get_content_charset('utf-8')
	resp_str = resp.read().decode(charset)
	resp_str = resp_str.replace('&nbsp;', '')

	return resp_str


def _load_trades(page):
	trades = []

	for mo in _rrows.finditer(page):
		if 'list00' in mo.group(0):
			continue

		try:
			trades.append(
				Trade.from_table_row(mo.group(0))
			)
		except ValueError as exc:
			print("Error: %r" % exc)

	return trades


if __name__ == '__main__':
	import code
	print_dupe()
	code.InteractiveConsole().raw_input(prompt='Press Enter to exit...')
