DELETE FROM "trades" WHERE `cost` = 0 OR `count` = 0;

ALTER TABLE "trades" ADD COLUMN `item_name_ru` VARCHAR;

CREATE TABLE "_new_trades" (
	`id`	INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
	`item_name`	VARCHAR,
	`owner_name`	VARCHAR,
	`count`	INTEGER CHECK (`count` > 0),
	`cost`	INTEGER CHECK (`cost` > 0),
	`city`	VARCHAR,
	`type`	INTEGER CHECK (`type` IN (1, 2)),
	`date`	DATETIME,
	`latest`	BOOLEAN DEFAULT 0,
	`item_id`	INTEGER
);

INSERT INTO "_new_trades" SELECT `id`,`item_name`, `owner_name`,`count`,`cost`,`city`,`type`,`date`,`latest`,`img_id` FROM `trades`;

DROP TABLE `trades`;

ALTER TABLE `_new_trades` RENAME TO `trades`;

CREATE UNIQUE INDEX iTrade
            ON trades (date, owner_name, item_name, cost);
