BEGIN TRANSACTION;
CREATE TABLE IF NOT EXISTS `workflow` (
	`wf_id`	INTEGER,
	`market`	TEXT,
	`trade`	TEXT,
	`currency`	TEXT,
	`tp`	FLOAT,
	`sl`	FLOAT,
	`sell_portion`	FLOAT,
	`sum_q`	FLOAT,
	`avg_price`	FLOAT,
	`run_mode`	TEXT,
	`price_entry`	FLOAT,
	`exchange`	TEXT,
	`userid`	INTEGER,
	`core_strategy`	TEXT DEFAULT 'standard',
	PRIMARY KEY(`wf_id`)
);
CREATE TABLE IF NOT EXISTS `user_params` (
	`id`	INTEGER,
	`userid`	INTEGER,
	`param_name`	TEXT,
	`param_val`	TEXT,
	`core_strategy`	TEXT DEFAULT 'standard',
	PRIMARY KEY(`id`)
);
CREATE TABLE IF NOT EXISTS `user_info` (
	`id`	INTEGER,
	`userid`	INTEGER,
	`name`	INTEGER,
	`active_strategy`	TEXT DEFAULT 'standard',
	PRIMARY KEY(`id`)
);
CREATE TABLE IF NOT EXISTS `user_balances` (
	`id`	INTEGER,
	`userid`	INTEGER,
	`balance`	REAL,
	`timestamp`	INTEGER,
	`core_strategy`	TEXT DEFAULT 'standard',
	PRIMARY KEY(`id`)
);
CREATE TABLE IF NOT EXISTS `trade_log` (
	`id`	INTEGER,
	`userid`	INTEGER,
	`start_timestamp`	INTEGER,
	`end_timestamp`	INTEGER,
	`trade_outcome`	REAL,
	`trade_commissions`	REAL,
	`trade_funding`	REAL,
	`earned_ratio`	REAL,
	`percent_gained`	REAL,
	`core_strategy`	TEXT DEFAULT 'standard',
	PRIMARY KEY(`id`)
);
CREATE TABLE IF NOT EXISTS `system` (
	`param_name`	TEXT,
	`param_val`	TEXT
);
CREATE TABLE IF NOT EXISTS `strategies` (
	`id`	INTEGER,
	`name`	TEXT,
	`description`	TEXT DEFAULT 0,
	PRIMARY KEY(`id`)
);
CREATE TABLE IF NOT EXISTS `markets` (
	`id`	INTEGER,
	`market`	TEXT,
	`description`	TEXT,
	PRIMARY KEY(`id`)
);
CREATE TABLE IF NOT EXISTS `market_info` (
	`id`	INTEGER,
	`market`	TEXT,
	`td_current_no`	INTEGER,
	`td_previous_no`	INTEGER,
	`td_current_direction`	TEXT,
	`td_previous_direction`	NUMERIC,
	`rsi_4h`	REAL,
	`rsi_1h`	REAL,
	`price`	REAL,
	`prediction`	TEXT,
	`probability`	REAL,
	`last_update`	INTEGER,
	PRIMARY KEY(`id`)
);
CREATE TABLE IF NOT EXISTS `losses` (
	`id`	INTEGER,
	`market`	TEXT,
	`count`	INT,
	`userid`	INTEGER,
	PRIMARY KEY(`id`)
);
CREATE TABLE IF NOT EXISTS `longs` (
	`long_id`	INTEGER,
	`market`	TEXT,
	`ep`	FLOAT,
	`quantity`	FLOAT,
	`exchange`	TEXT,
	`userid`	INTEGER,
	PRIMARY KEY(`long_id`)
);
CREATE TABLE IF NOT EXISTS `labels_generated_prices` (
	`timestamp`	TIMESTAMP,
	`price`	REAL,
	`market`	TEXT
);
CREATE TABLE IF NOT EXISTS `labels_generated` (
	`timestamp`	TIMESTAMP,
	`rsi_1h`	REAL,
	`td_setup_1h`	INTEGER,
	`td_direction_1h`	INTEGER,
	`if_countdown_down_1h`	INTEGER,
	`if_countdown_up_1h`	INTEGER,
	`countdown_up_1h`	INTEGER,
	`countdown_down_1h`	INTEGER,
	`ma_30_1h`	REAL,
	`ma_20_1h`	REAL,
	`ma_10_1h`	REAL,
	`close_percent_change_1h`	REAL,
	`rsi_percent_change_1h`	REAL,
	`high_to_close_1h`	REAL,
	`low_to_close_1h`	REAL,
	`close_to_ma10_1h`	REAL,
	`close_to_ma20_1h`	REAL,
	`close_to_ma30_1h`	REAL,
	`rsi_4h`	REAL,
	`td_setup_4h`	INTEGER,
	`td_direction_4h`	INTEGER,
	`if_countdown_down_4h`	INTEGER,
	`if_countdown_up_4h`	INTEGER,
	`countdown_up_4h`	INTEGER,
	`countdown_down_4h`	INTEGER,
	`ma_30_4h`	REAL,
	`ma_20_4h`	REAL,
	`ma_10_4h`	REAL,
	`close_percent_change_4h`	REAL,
	`rsi_percent_change_4h`	REAL,
	`high_to_close_4h`	REAL,
	`low_to_close_4h`	REAL,
	`close_to_ma10_4h`	REAL,
	`close_to_ma20_4h`	REAL,
	`close_to_ma30_4h`	REAL,
	`rsi_1d`	REAL,
	`td_setup_1d`	INTEGER,
	`td_direction_1d`	INTEGER,
	`if_countdown_down_1d`	INTEGER,
	`if_countdown_up_1d`	INTEGER,
	`countdown_up_1d`	INTEGER,
	`countdown_down_1d`	INTEGER,
	`ma_30_1d`	REAL,
	`ma_20_1d`	REAL,
	`ma_10_1d`	REAL,
	`close_percent_change_1d`	REAL,
	`rsi_percent_change_1d`	REAL,
	`high_to_close_1d`	REAL,
	`low_to_close_1d`	REAL,
	`close_to_ma10_1d`	REAL,
	`close_to_ma20_1d`	REAL,
	`close_to_ma30_1d`	REAL,
	`exchange`	TEXT,
	`market`	TEXT
);
CREATE TABLE IF NOT EXISTS `keys` (
	`id`	INTEGER PRIMARY KEY AUTOINCREMENT,
	`user`	TEXT,
	`key_id`	TEXT,
	`key_secret`	TEXT,
	`strategy`	TEXT DEFAULT 'standard',
	`exchange`	TEXT
);
CREATE TABLE IF NOT EXISTS `jobs` (
	`job_id`	INTEGER,
	`market`	TEXT,
	`tp`	FLOAT,
	`sl`	FLOAT,
	`simulation`	INT,
	`mooning`	INT,
	`selling`	INT,
	`price_curr`	FLOAT,
	`percent_of`	FLOAT,
	`abort_flag`	INT,
	`stop_loss`	INT,
	`entry_price`	FLOAT,
	`mode`	TEXT,
	`tp_p`	FLOAT,
	`sl_p`	FLOAT,
	`exchange`	TEXT,
	`userid`	INTEGER,
	`sl_cutoff`	REAL,
	`core_strategy`	TEXT DEFAULT 'standard',
	`short_flag`	INTEGER,
	PRIMARY KEY(`job_id`)
);
CREATE TABLE IF NOT EXISTS `buys` (
	`job_id`	INTEGER,
	`market`	TEXT,
	`price_fixed`	INT,
	`price`	FLOAT,
	`abort_flag`	INT,
	`source_position`	FLOAT,
	`mode`	TEXT,
	`exchange`	TEXT,
	`userid`	INTEGER,
	`core_strategy`	TEXT DEFAULT 'standard',
	PRIMARY KEY(`job_id`)
);
CREATE TABLE IF NOT EXISTS `buy_hold` (
	`job_id`	INTEGER,
	`market`	TEXT,
	`price_fixed`	INT,
	`price`	FLOAT,
	`abort_flag`	INT,
	`source_position`	FLOAT,
	`mode`	TEXT,
	`exchange`	TEXT,
	`userid`	INTEGER,
	`core_strategy`	TEXT DEFAULT 'standard',
	PRIMARY KEY(`job_id`)
);
CREATE TABLE IF NOT EXISTS `bback` (
	`id`	INTEGER,
	`market`	TEXT,
	`bb_price`	FLOAT,
	`curr_price`	FLOAT,
	`trade_price`	FLOAT,
	`abort_flag`	INT,
	`exchange`	TEXT,
	`userid`	INTEGER,
	`core_strategy`	TEXT DEFAULT 'standard',
	`bb_price_margin`	REAL,
	PRIMARY KEY(`id`)
);
CREATE INDEX IF NOT EXISTS `ix_labels_generated_timestamp` ON `labels_generated` (
	`timestamp`
);
CREATE INDEX IF NOT EXISTS `ix_labels_generated_prices_timestamp` ON `labels_generated_prices` (
	`timestamp`
);
COMMIT;
