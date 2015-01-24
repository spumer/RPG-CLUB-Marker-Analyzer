# encoding: utf-8


import re
import sqlite3
import datetime
import itertools
import urllib.error
import urllib.request

from contextlib import closing
from contextlib import contextmanager


SQLITE_EXEC_ARG_LIMIT = 999
SQLITE_DB_FILENAME = 'market_history.db'

_rbulk = re.compile(r'\s\*$')
_rtag = re.compile(r'</?\w+[^>]*>*')

_rrows = re.compile(r'<tr[^>]*>\s*(?:<td[^>]*>.*?</td>\s*){8}', flags=re.IGNORECASE)
_ritems = re.compile(r'<td[^>]*>\s*(.*?)\s*</td>', flags=re.IGNORECASE)


def take(iterable, n):
    """Return first n items of the iterable as a list"""
    return list(itertools.islice(iterable, n))


def tag_split(txt):
    return [x for x in _rtag.split(txt) if x]


class Trade:
    def __init__(self, date, owner_name, city, item_name, count, cost, img_id=None, bulk=False):
        self.date = date
        self.owner_name = owner_name
        self.city = city
        self.item_name = item_name
        self.count = count
        self.cost = cost
        self.img_id = img_id
        self.bulk = bulk

    def __repr__(self):
        return (
            'Item: {item_name}, Owner: {owner_name}, City: {city}, Date: {date}, '
            'Count: {count}, Cost: {cost}'.format(
                item_name=self.item_name,
                owner_name=self.owner_name,
                city=self.city,
                date=self.date,
                count=self.count,
                cost=self.cost,
            )
        )

    def __eq__(self, other):
        if not isinstance(other, Trade):
            return False

        for attr in ('date', 'owner_name', 'city', 'item_name', 'cost', 'bulk'):
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
            + hash(self.bulk)
        )

    @staticmethod
    def _extract_img_id(tag, _rsrc=re.compile(r'src="[^"]*?(\d+)[^"]*?"')):
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
        date, owner_city, img_tag, item_name_ru_en, _, count, _, cost = _ritems.findall(row)

        img_id = cls._extract_img_id(img_tag)
        date = cls._extract_date(date)

        owner_name, city = tag_split(owner_city)
        owner_name = _rbulk.sub('', owner_name)
        owner_name = owner_name.strip()

        bulk = '*' in cost

        cost = cost.replace('.', '')
        cost = _rbulk.sub('', cost)

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

        return cls(date, owner_name, city, item_name_en, int(count), int(cost), img_id, bulk)


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
                resp = urllib.request.urlopen(addr)
            except urllib.error.HTTPError as exc:
                retry -= 1
                if not retry:
                    raise
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
            if 'list00' in mo.group(0):
                continue

            try:
                trade = Trade.from_table_row(mo.group(0))
            except ValueError as exc:
                print("Error: %r" % exc)
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
                            AND `item_name` = ?
                            AND `owner_name` = ?
                            AND `cost` = ?
                        ''',
                        (t.date, t.item_name, t.owner_name, t.cost)
                    )

                    res = cur.fetchone()
                    if res:
                        # we have this trade already, ignore
                        ignore_ids.append(res[0])
                        continue

                    new_trades.append((
                        t.item_name,
                        t.owner_name,
                        t.count,
                        t.cost,
                        t.city,
                        t.date,
                        type_,
                        latest,
                        t.img_id,
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
                    `item_name`, `owner_name`, `count`, `cost`, `city`, `date`, `type`, `latest`, `img_id`
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
                `item_name`,
                `owner_name`,
                `count`,
                `cost`,
                `city`,
                `type`,
                `date` as "[timestamp]",
                `img_id`
            FROM
                `trades`
            '''
        if latest_only:
            q += ' WHERE `latest` = 1'

        with sqlite_conn() as conn:
            cur = conn.cursor()
            cur.execute(q)

            demands = []
            offers = []
            for row in cur:
                item_name, owner_name, count, cost, city, type_, date, img_id = row
                trade = Trade(date, owner_name, city, item_name, count, cost, img_id=img_id)

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


def sqlite_init_trades(filename=SQLITE_DB_FILENAME):
    with sqlite_conn(filename=filename) as conn:
        cur = conn.cursor()
        cur.execute(
            '''
            CREATE TABLE IF NOT EXISTS `trades` (
                `id` INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
                `item_name` VARCHAR,
                `owner_name` VARCHAR,
                `count` INTEGER,
                `cost` INTEGER,
                `city` VARCHAR,
                `type` INTEGER,  -- 1 - demand, 2 - offer
                `date` DATETIME,
                `latest` BOOLEAN DEFAULT 0,
                `img_id` INTEGER
            )
            '''
        )
        cur.execute(
            '''
            CREATE UNIQUE INDEX iTrade
            ON `trades` (`date`, `owner_name`, `item_name`, `cost`)
            '''
        )
