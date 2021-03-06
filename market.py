# encoding: utf-8


import re
import sqlite3
import datetime
import itertools
import http.client
import urllib.error
import urllib.request

from contextlib import closing
from contextlib import contextmanager


class OwnerCitySplitError(Exception):
    pass


class ItemNameSplitError(Exception):
    pass


class EmptyAmountError(Exception):
    pass


SQLITE_DB_FILENAME = 'market_history.db'

_rbulk = re.compile(r'\s\*$')
_rtag = re.compile(r'</?\w+[^>]*>')

_rrows = re.compile(r'<tr[^>]*>\s*(?:<td[^>]*>.*?</td>\s*){8}', flags=re.IGNORECASE)
_ritems = re.compile(r'<td[^>]*>\s*(.*?)\s*</td>', flags=re.IGNORECASE)


def tag_split(txt):
    return [x for x in _rtag.split(txt) if x]


class Trade:
    def __init__(self, date, owner_name, city, item_name, mod, count, cost, item_id=None, bulk=False):
        self.date = date
        self.owner_name = owner_name
        self.city = city
        self._item_name = item_name
        self.mod = mod
        self.count = count
        self.cost = cost
        self.item_id = item_id
        self.bulk = bulk

    @property
    def item_name(self):
        return self._item_name + self.mod

    def __repr__(self):
        return (
            'Item: {item_name}, Owner: {owner_name}, City: {city}, Date: {date}, '
            'Count: {count}, Cost: {cost}, ID: {item_id}'.format(
                item_name=self.item_name,
                owner_name=self.owner_name,
                city=self.city,
                date=self.date,
                count=self.count,
                cost=self.cost,
                item_id=self.item_id,
            )
        )

    def __eq__(self, other):
        if not isinstance(other, Trade):
            return False

        for attr in ('date', 'owner_name', 'city', 'item_name', 'cost', 'item_id', 'bulk'):
            if getattr(self, attr) != getattr(other, attr):
                return False

        return True

    def __hash__(self):
        return (
            hash(self.date)
            + hash(self.owner_name)
            + hash(self.city)
            + hash(self.item_name)
            + hash(self.cost)
            + hash(self.item_id)
            + hash(self.bulk)
        )

    @staticmethod
    def _extract_item_id(tag, _rsrc=re.compile(r'src="[^"]*?(\d+)[^"]*?"')):
        mo = _rsrc.search(tag)
        if mo:
            return int(mo.group(1))

        return None

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
        date, owner_city, img_tag, item_name_en_ru, _, count, _, cost = _ritems.findall(row)

        item_id = cls._extract_item_id(img_tag)
        date = cls._extract_date(date)

        try:
            owner_name, city = tag_split(owner_city)
            owner_name = _rbulk.sub('', owner_name)
            owner_name = owner_name.strip()
        except ValueError as exc:
            raise OwnerCitySplitError from exc

        bulk = '*' in cost

        cost = cost.replace('.', '')
        cost = _rbulk.sub('', cost)

        if not count.isdigit() or not cost.isdigit():
            raise EmptyAmountError

        name_parts = tag_split(item_name_en_ru)
        mod = ''

        try:
            if len(name_parts) > 2:
                # example:  ['Baby Kookaburra Ocarina', 'Окарина Детеныша Кукабарры', '+63']
                item_name_en, item_name_ru, mod = name_parts
            elif len(name_parts) > 1:
                item_name_en, item_name_ru = name_parts
            else:
                item_name_en = item_name_ru = name_parts[0]
        except ValueError as exc:
            raise ItemNameSplitError from exc

        # example: ['none', 'Тиара Снежной Королевы']
        if item_name_en.lower() == 'none' and item_name_ru:
            item_name_en = item_name_ru

        return cls(date, owner_name, city, item_name_en, mod, int(count), int(cost), item_id, bulk)


class TradeList:
    demands_url = 'http://market.bot.rpg-club.com/motherland/buy/price/desc'
    offers_url = 'http://market.bot.rpg-club.com/motherland/sell/price/asc'

    def __init__(self, demands=None, offers=None):
        if demands is None:
            demands = []

        if offers is None:
            offers = []

        self.demands = demands
        self.offers = offers

    @staticmethod
    def _read_page(addr, retry=3):
        while True:
            try:
                resp = urllib.request.urlopen(addr, timeout=60)
            except (urllib.error.HTTPError, http.client.HTTPException) as exc:
                if not retry:
                    raise
                retry -= 1
                print("Error, retry %s: %r" % (retry, exc))
            else:
                break

        charset = resp.headers.get_content_charset('utf-8')
        resp_str = resp.read().decode(charset)
        resp_str = resp_str.replace('&nbsp;', ' ')

        return resp_str

    @staticmethod
    def _read_trades(page):
        trades = {}

        for mo in _rrows.finditer(page):
            mo_value = mo.group(0)
            if 'list00' in mo_value:
                continue

            try:
                trade = Trade.from_table_row(mo_value)
            except (OwnerCitySplitError, ItemNameSplitError, EmptyAmountError):
                # Temporary errors
                continue
            except ValueError as exc:
                print("Error: %r, data: %r" % (exc, mo_value))
                continue

            if trade.cost <= 0 or trade.count <= 0:
                continue

            if trade in trades:
                # Trader sell more than one unique item
                # Example: soul crystals, any weapon or armor, etc.
                trades[trade].count += trade.count
            elif not trade.bulk:
                trades[trade] = trade

        return list(trades.values())

    def write(self, latest=False):
        ignore_ids = []
        new_trades = []

        with sqlite_conn() as conn:
            cur = conn.cursor()

            # make a decision for each trade: add or ignore
            for trades, type_ in ((self.demands, 1), (self.offers, 2)):
                for t in trades:
                    cur.execute(
                        '''
                        SELECT
                            `id`
                        FROM
                            `trades`
                        WHERE
                            `date` = ?
                            AND `mod` = ?
                            AND `owner_name` = ?
                            AND `cost` = ?
                            AND `item_id` = ?
                        ''',
                        (t.date, t.mod, t.owner_name, t.cost, t.item_id)
                    )

                    res = cur.fetchone()
                    if res:
                        # we have this trade already, ignore
                        ignore_ids.append(res[0])
                        continue

                    new_trades.append((
                        t.mod,
                        t.owner_name,
                        t.count,
                        t.cost,
                        t.city,
                        t.date,
                        type_,
                        latest,
                        t.item_id,
                    ))

            if not new_trades:
                return False

            # Reset `latest` status for old trades
            if latest:
                expr_in = ','.join(str(i) for i in ignore_ids)
                cur.execute(
                    'UPDATE `trades` SET `latest` = 0 WHERE `latest` = 1 AND `id` NOT IN (%s)' % expr_in
                )

            # Insert new trades
            cur.executemany(
                '''
                INSERT INTO trades (
                    `mod`, `owner_name`, `count`, `cost`, `city`, `date`, `type`, `latest`, `item_id`
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                ''',
                new_trades
            )

        return len(new_trades) != 0

    @classmethod
    def from_local(cls, latest_only=True):
        q = '''
            SELECT
                `items`.`name`,
                `mod`,
                `owner_name`,
                `count`,
                `cost`,
                `city`,
                `type`,
                `date` as "[timestamp]",
                `item_id`
            FROM
                `trades`
                INNER JOIN `items` ON `trades`.`item_id` = `items`.`id`
            '''
        if latest_only:
            q += ' WHERE `latest` = 1'

        with sqlite_conn() as conn:
            cur = conn.cursor()
            cur.execute(q)

            demands = []
            offers = []
            for row in cur:
                item_name, mod, owner_name, count, cost, city, type_, date, item_id = row
                trade = Trade(date, owner_name, city, item_name, mod or '', count, cost, item_id=item_id)

                if type_ == 1:
                    demands.append(trade)
                elif type_ == 2:
                    offers.append(trade)
                else:
                    raise NotImplementedError

        return cls(demands=demands, offers=offers)


    @classmethod
    def from_remote(cls):
        demands = cls._read_trades(cls._read_page(cls.demands_url))
        offers = cls._read_trades(cls._read_page(cls.offers_url))
        return cls(demands=demands, offers=offers)


def get_trades(remote=False):
    if remote:
        return TradeList.from_remote()
    return TradeList.from_local()


@contextmanager
def sqlite_conn(filename=SQLITE_DB_FILENAME, autocommit=True):
    with closing(sqlite3.connect(
        filename, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    ) as conn:
        yield conn
        if autocommit:
            conn.commit()


def sqlite_init_items(filename=SQLITE_DB_FILENAME):
    with sqlite_conn(filename=filename) as conn:
        cur = conn.cursor()
        cur.execute(
            '''
            CREATE TABLE "items" (
                `id`    INTEGER NOT NULL PRIMARY KEY,
                `name`  VARCHAR
            )
            '''
        )
        cur.execute('CREATE UNIQUE INDEX iID ON `items` (`id`)')


def sqlite_init_trades(filename=SQLITE_DB_FILENAME):
    with sqlite_conn(filename=filename) as conn:
        cur = conn.cursor()
        cur.execute(
            '''
            CREATE TABLE "trades" (
                `id`    INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                `item_name` VARCHAR,
                `mod` VARCHAR,
                `owner_name`    VARCHAR,
                `count` INTEGER CHECK (`count` > 0),
                `cost`  INTEGER CHECK (`cost` > 0),
                `city`  VARCHAR,
                `type`  INTEGER CHECK (`type` IN (1, 2)),  -- 1 demand (buy), 2 -- offer (sell)
                `date`  DATETIME,
                `latest`    BOOLEAN DEFAULT 0,
                `item_id` INTEGER,
                FOREIGN KEY(`item_id`) REFERENCES "items"(`id`)
            )
            '''
        )
        cur.execute(
            '''
            CREATE UNIQUE INDEX iTrade
            ON `trades` (`date`, `owner_name`, `mod`, `cost`, `item_id`)
            '''
        )
