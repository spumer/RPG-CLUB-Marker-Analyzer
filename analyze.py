# encoding: utf-8

import collections

import market


IMG_BASE_URL = 'http://market.bot.rpg-club.com/img/%(img_id)s.png'


class Dupe:
   def __init__(self, demand, offer):
      buy_count = min(demand.count, offer.count)
      equity = buy_count * (demand.cost - offer.cost)

      self.demand = demand
      self.offer = offer

      self.equity = equity
      self.buy_count = buy_count

   def to_dict(self):
      return {
         'item_name': self.offer.item_name,
         'equity': self.equity,
         'buy_count': self.buy_count,
         'required_aden': self.buy_count * self.offer.cost,
         'img_url': None if self.offer.img_id is None else IMG_BASE_URL % {'img_id': self.offer.img_id},
         'seller': {
            'name': self.offer.owner_name,
            'city': self.offer.city,
            'date': int(self.offer.date.timestamp()),
         },
         'buyer': {
            'name': self.demand.owner_name,
            'city': self.demand.city,
            'date': int(self.demand.date.timestamp()),
         },
      }

   def to_msg(self):
      return (
         '''Dupe '{item_name}', equity {equity} aden, required {total_price} aden:\n'''
         '''\tbuy {count} from "{seller_name}" ({seller_city}),\n'''
         '''\tsell to "{buyer_name}" ({buyer_city})'''.format(
         item_name=self.offer.item_name,
         equity=self.equity,
         total_price=self.buy_count * self.offer.cost,
         count=self.buy_count,
         seller_name=self.offer.owner_name,
         seller_city=self.offer.city,
         buyer_name=self.demand.owner_name,
         buyer_city=self.demand.city,
      ))


def get_dupes():
   dupes = []

   trades = market.get_trades()

   offers = collections.defaultdict(list)
   for o in trades.offers:
      offers[o.item_name].append(o)
      offers[o.item_name].sort(key=lambda x: (x.cost, -x.count))  # cost asc, count desc

   for demand in sorted(trades.demands, key=lambda x: (x.cost, x.count), reverse=True):  # cost desc, count desc
      item_offers = offers.get(demand.item_name)

      if not item_offers:
         continue

      dupe_offers = [o for o in item_offers if o.count and o.cost < demand.cost]
      if not dupe_offers:
         continue

      while demand.count:
         offer = next((o for o in dupe_offers if o.count and not o.bulk), None)
         if offer is None:
            break

         dupe = Dupe(demand, offer)
         if dupe.buy_count:
            dupes.append(dupe)

            demand.count -= dupe.buy_count
            offer.count -= dupe.buy_count

   return dupes
