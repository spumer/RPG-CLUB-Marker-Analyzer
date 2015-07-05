# encoding: utf-8

# RPG-CLUB Market Analyzer 1.2.0

# Changelog:
# 1.2.0 - show all dupe offers for each item, not only best
# 1.1.0 - add printing dupe chain
# 1.0.1 - fix dupe analyze logic
# 1.0.0 - initial release


import collections

import market


class Dupe:
	def __init__(self, offer, demand):
		buy_count = min(demand.count,  offer.count)
		equity = buy_count * (demand.cost - offer.cost)

		if buy_count:
			offer.count -= buy_count
			demand.count -= buy_count

		self.offer = offer
		self.demand = demand

		self.equity = equity
		self.buy_count = buy_count

	def to_string(self):
		return '''Dupe '{item_name}', equity {equity} aden, required {total_price} aden:\n'''
			'''\tbuy {count} from "{seller_name}" ({seller_city}),\n'''
			'''\tsell to "{buyer_name}" ({buyer_city})'''.format(
			item_name=self.offer.item_name,
			equity=self.equity,
			total_price=self.buy_count * offer.cost,
			count=self.buy_count,
			seller_name=self.offer.owner_name,
			seller_city=self.offer.city,
			buyer_name=self.demand.owner_name,
			buyer_city=self.demand.city,
		)


def print_dupe():
	if not dupes:
		print("Sorry, dupe not found")
	else:
		print("Great! Dupe was found!")
		for demand, offers in dupes:


			print(
,
				end='\n\n'
			)


def get_dupes():
	dupes = []

	offers = collections.defaultdict(list)
	for o in market.download_actual_offers():
		offers[o.item_name].append(o)
		offers[o.item_name].sort(key=lambda x: (x.cost, -x.count))  # cost asc, count desc

	for d in market.download_actual_demands():
		item_offers = offers.get(d.item_name)

		if not item_offers:
			continue

		offers = [o for o in item_offers if o.cost < d.cost]
		if not offers:
			continue

		offer = next((o for o in offers if o.count), None)
		if offer is not None:
			dupes.append(Dupe(d, offer))

	return dupes

if __name__ == '__main__':
	import code
	print_dupe()
	code.InteractiveConsole().raw_input(prompt='Press Enter to exit...')
