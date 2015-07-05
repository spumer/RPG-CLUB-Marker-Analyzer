import re
import sqlite3

from market import sqlite_conn
from market import sqlite_init_items


_rmod = re.compile(r'.*?(\+\d+)')


def cleanup_trades():
	with sqlite_conn() as conn:
		conn.execute('DELETE FROM `trades` WHERE item_id = 201330543')
		conn.execute('DELETE FROM `trades` WHERE item_id IS NULL')


def update_table_items():
	cmds = []
	with open('items.sql') as fstream:
		cmds.extend(
			fstream.read().split(';')
		)

	# RPG-club custom items
	cmds.extend((
		"INSERT INTO items (id, name) VALUES (26164, 'Libaesun helmet');",
		"INSERT INTO items (id, name) VALUES (26610, 'None');",
		"INSERT INTO items (id, name) VALUES (26611, 'None');",
		"INSERT INTO items (id, name) VALUES (26612, 'None');",
		"INSERT INTO items (id, name) VALUES (27019, 'Chronicler''s Letter');",
		"INSERT INTO items (id, name) VALUES (27023, 'RUR');",
	))

	with sqlite_conn() as conn:
		cur = conn.cursor()
		for cmd in cmds:
			cur.execute(cmd)


def updata_table_trades():
	cmds = (
		'ALTER TABLE "trades" ADD COLUMN `mod` VARCHAR;',
		'''
		CREATE TABLE "_new_trades" (
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
			`item_id`   REFERENCES items(id)
		);
		''',
		'INSERT INTO "_new_trades" SELECT `id`,`item_name`, `mod`, `owner_name`,`count`,`cost`,`city`,`type`,`date`,`latest`,`item_id` FROM `trades`;',
		'DROP TABLE `trades`;',
		'ALTER TABLE `_new_trades` RENAME TO `trades`;',
		'CREATE UNIQUE INDEX iTrade ON `trades` (`date`, `owner_name`, `mod`, `cost`, `item_id`);',
	)

	with sqlite_conn() as conn:
		cur = conn.cursor()
		for cmd in cmds:
			try:
				cur.execute(cmd)
			except Exception:
				print('Exception in: %r' % cmd)
				raise


def fill_mod_column():
	with sqlite_conn() as conn:
		cur = conn.cursor()
		cur.execute(
			'''
			SELECT DISTINCT `trades`.`id`, item_name
			FROM
				trades
				INNER JOIN items ON trades.item_id = items.id
			WHERE
				lower(trim(trades.item_name)) <> lower(trim(items.name))
				AND item_name LIKE '%+%'
			'''
		)

		updates = []
		for row in cur:
			mo = _rmod.search(row[1])
			if mo:
				mod = mo.group(1)
				updates.append((mod, row[0]))
			else:
				raise NotImplementedError

		for u in updates:
			try:
				cur.execute('UPDATE trades SET mod = ? WHERE id = ?', u)
			except sqlite3.IntegrityError:
				cur.execute('DELETE FROM trades WHERE id = ?', (u[1],))


if __name__ == '__main__':
	sqlite_init_items()
	update_table_items()

	cleanup_trades()
	updata_table_trades()
	fill_mod_column()
