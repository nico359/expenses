-- MyExpenses-compatible schema template

-- Generated from a real MyExpenses backup (schema version 191).

PRAGMA foreign_keys=OFF;

PRAGMA journal_mode=DELETE;

BEGIN TRANSACTION;

CREATE TABLE _sync_state (status integer );

CREATE TABLE account_attributes (
    account_id integer references accounts(_id) ON DELETE CASCADE,
    attribute_id integer references attributes(_id) ON DELETE CASCADE,
    value text not null,
    primary key (account_id, attribute_id)
);

CREATE TABLE account_exchangerates (account_id integer not null references accounts(_id) ON DELETE CASCADE,currency_self text not null, currency_other text not null, exchange_rate real not null, UNIQUE (account_id,currency_self,currency_other));

CREATE TABLE account_flags (
    _id integer primary key autoincrement,
    flag_label text unique not null,
    flag_sort_key integer not null default 0,
    flag_icon text,
    visible boolean not null
);

CREATE TABLE account_types (
    _id integer primary key autoincrement,
    label text not null,
    type_sort_key integer not null default 0,
    isAsset boolean not null,
    supportsReconciliation boolean not null
);

CREATE TABLE accounts (
        _id integer primary key autoincrement,
        label text not null,
        opening_balance integer,
        description text,
        currency text not null references currency(code),
        type integer references account_types(_id) NOT NULL,
        color integer default -3355444,
        grouping text not null check (grouping in ('NONE','DAY','WEEK','MONTH','YEAR')) default 'NONE',
        usages integer default 0,
        last_used datetime,
        sort_key integer,
        sync_account_name text,
        sync_sequence_local integer default 0,
        exclude_from_totals boolean default 0,
        uuid text,
        sort_by text default 'date',
        sort_direction text not null check (sort_direction in ('ASC','DESC')) default 'DESC',
        criterion integer,
        flag integer references account_flags(_id) NOT NULL default 0,
        sealed boolean default 0,
        dynamic boolean default 0,
        is_portfolio boolean default 0,
        bank_id integer references banks(_id) ON DELETE SET NULL,
        parent_id integer references accounts(_id) ON DELETE CASCADE,
        balance_type not null check (balance_type in ('CURRENT','TOTAL','CLEARED','RECONCILED','DELTA','VALUATION')) default 'CURRENT');

CREATE TABLE accounts_tags ( tag_id integer references tags(_id) ON DELETE CASCADE, account_id integer references accounts(_id) ON DELETE CASCADE, primary key (tag_id,account_id));

CREATE TABLE accounttype_paymentmethod (type integer references account_types(_id), method_id integer references paymentmethods(_id), primary key (type,method_id));

CREATE TABLE android_metadata (locale TEXT);

CREATE TABLE attachments (
    _id integer primary key autoincrement,
    uri text not null unique,
    uuid text not null unique
);

CREATE TABLE attributes (
    _id integer primary key autoincrement,
    attribute_name text not null,
    context text not null,
    unique (attribute_name, context)
);

CREATE TABLE banks (_id integer primary key autoincrement, blz text not null, bic text not null, name text not null, user_id text not null, version interger not null, unique(blz, user_id));

CREATE TABLE budget_allocations ( budget_id integer not null references budgets(_id) ON DELETE CASCADE, cat_id integer not null references categories(_id) ON DELETE CASCADE, year integer, second integer, budget integer, rollOverPrevious integer, rollOverNext integer, oneTime boolean default 0, primary key (budget_id,cat_id,year,second));

CREATE TABLE budgets ( _id integer primary key autoincrement, title text not null default '', description text not null, grouping text not null check (grouping in ('NONE','DAY','WEEK','MONTH','YEAR')), account_id integer references accounts(_id) ON DELETE CASCADE, currency text, start datetime, end datetime, is_default boolean default 0, uuid text);

CREATE TABLE categories (_id integer primary key autoincrement, label text not null, label_normalized text,parent_id integer references categories(_id) ON DELETE CASCADE, usages integer default 0, last_used datetime, color integer, icon string, uuid text, type integer, UNIQUE (label,parent_id));

CREATE TABLE changes ( account_id integer not null references accounts(_id) ON DELETE CASCADE,type text not null check (type in ('created','updated','deleted','unsplit','metadata','link','tags','attachments','unarchive')), sync_sequence_local integer, uuid text not null, timestamp datetime DEFAULT (strftime('%s','now')), parent_uuid text, comment text, date datetime, value_date datetime, amount integer, original_amount integer, original_currency text, equivalent_amount integer, cat_id integer references categories(_id) ON DELETE SET NULL, payee_id integer references payee(_id) ON DELETE SET NULL, transfer_account integer references accounts(_id) ON DELETE SET NULL,method_id integer references paymentmethods(_id) ON DELETE SET NULL,cr_status text check (cr_status in ('UNRECONCILED','CLEARED','RECONCILED','VOID')),status integer default 0, number text);

CREATE TABLE currency (_id integer primary key autoincrement, code text UNIQUE not null,grouping text not null check (grouping in ('NONE','DAY','WEEK','MONTH','YEAR')) default 'NONE',sort_by text default 'date', sort_direction text not null check (sort_direction in ('ASC','DESC')) default 'DESC',label text,fraction_digits integer,symbol text,commodity_type text);

CREATE TABLE debts (_id integer primary key autoincrement, payee_id integer references payee(_id) ON DELETE CASCADE, date datetime not null, label text not null, amount integer, equivalent_amount integer,  currency text not null, description text, sealed boolean default 0);

CREATE TABLE equivalent_amounts (
    transaction_id integer NOT NULL references transactions(_id) ON DELETE CASCADE,
    currency text NOT NULL references currency (code) ON DELETE CASCADE,
    equivalent_amount integer NOT NULL,
    primary key (transaction_id, currency)
);

CREATE TABLE event_cache ( title TEXT,description TEXT,dtstart INTEGER,dtend INTEGER,eventTimezone TEXT,duration TEXT,allDay INTEGER NOT NULL DEFAULT 0,rrule TEXT,customAppPackage TEXT,customAppUri TEXT);

CREATE TABLE payee (
    _id integer primary key autoincrement,
    name text not null,
    short_name text,
    iban text,
    bic text,
    name_normalized text,
    parent_id integer references payee(_id) ON DELETE CASCADE,
    unique(name, iban));

CREATE TABLE paymentmethods (_id integer primary key autoincrement, label text not null, is_numbered boolean default 0, type integer check (type in (-1,0,1)) default 0, icon text);

CREATE TABLE planinstance_transaction ( template_id integer references templates(_id) ON DELETE CASCADE,instance_id integer,transaction_id integer UNIQUE references transactions(_id) ON DELETE CASCADE, primary key (template_id,instance_id));

CREATE TABLE prices (
    commodity text NOT NULL,
    currency text NOT NULL references currency (code) ON DELETE CASCADE,
    date datetime NOT NULL,
    source text NOT NULL,
    type text default 'unknown',
    value real not NULL,
    primary key(commodity, currency, date, source, type)
);

CREATE TABLE settings (key text unique not null, value text);

CREATE TABLE tags (
        _id integer primary key autoincrement,
        label text UNIQUE not null,
        color integer default null);

CREATE TABLE templates ( _id integer primary key autoincrement, comment text, amount integer not null, cat_id integer references categories(_id), account_id integer not null references accounts(_id) ON DELETE CASCADE,payee_id integer references payee(_id), transfer_account integer references accounts(_id) ON DELETE CASCADE,method_id integer references paymentmethods(_id), title text not null, usages integer default 0, plan_id integer, plan_execution boolean default 0, uuid text, last_used datetime, parent_id integer references templates(_id) ON DELETE CASCADE, status integer default 0, plan_execution_advance integer default 0, default_action text not null check (default_action in ('SAVE','EDIT')) default 'SAVE', original_amount integer, original_currency text, debt_id integer references debts(_id) ON DELETE SET NULL);

CREATE TABLE templates_tags ( tag_id integer references tags(_id) ON DELETE CASCADE, template_id integer references templates(_id) ON DELETE CASCADE, primary key (tag_id,template_id));

CREATE TABLE transaction_attachments (
    transaction_id integer references transactions(_id) ON DELETE CASCADE,
    attachment_id integer references attachments(_id),
    primary key (transaction_id, attachment_id)
);

CREATE TABLE transaction_attributes (
    transaction_id integer references transactions(_id) ON DELETE CASCADE,
    attribute_id integer references attributes(_id) ON DELETE CASCADE,
    value text not null,
    primary key (transaction_id, attribute_id)
);

CREATE TABLE transactions( _id integer primary key autoincrement, comment text, date datetime not null, value_date datetime not null, amount integer not null, cat_id integer references categories(_id), account_id integer not null references accounts(_id) ON DELETE CASCADE,payee_id integer references payee(_id), transfer_peer integer references transactions(_id), transfer_account integer references accounts(_id),method_id integer references paymentmethods(_id),parent_id integer references transactions(_id) ON DELETE CASCADE, status integer default 0, cr_status text not null check (cr_status in ('UNRECONCILED','CLEARED','RECONCILED','VOID')) default 'RECONCILED',number text, uuid text, original_amount integer, original_currency text, debt_id integer references debts(_id) ON DELETE SET NULL);

CREATE TABLE transactions_tags ( tag_id integer references tags(_id) ON DELETE CASCADE, transaction_id integer references transactions(_id) ON DELETE CASCADE, primary key (tag_id,transaction_id));

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (1, 'AFN', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (2, 'ALL', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (3, 'DZD', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (4, 'AOA', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (5, 'ARS', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (6, 'AMD', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (7, 'AWG', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (8, 'AUD', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (9, 'AZN', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (10, 'BSD', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (11, 'BHD', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (12, 'BDT', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (13, 'BBD', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (14, 'BYN', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (15, 'BZD', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (16, 'BMD', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (17, 'BTN', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (18, 'BOB', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (19, 'BAM', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (20, 'BWP', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (21, 'BRL', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (22, 'BND', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (23, 'BGN', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (24, 'BIF', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (25, 'KHR', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (26, 'CAD', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (27, 'CVE', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (28, 'KYD', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (29, 'XOF', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (30, 'XAF', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (31, 'XPF', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (32, 'CLP', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (33, 'CNY', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (34, 'COP', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (35, 'KMF', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (36, 'CDF', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (37, 'CRC', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (38, 'HRK', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (39, 'CUP', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (40, 'CUC', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (41, 'CZK', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (42, 'DKK', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (43, 'DJF', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (44, 'DOP', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (45, 'XCD', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (46, 'EGP', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (47, 'SVC', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (48, 'ERN', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (49, 'ETB', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (50, 'EUR', 'NONE', 'date', 'DESC', NULL, 2, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (51, 'FKP', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (52, 'FJD', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (53, 'GMD', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (54, 'GEL', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (55, 'GHS', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (56, 'GIP', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (57, 'GTQ', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (58, 'GNF', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (59, 'GYD', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (60, 'HTG', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (61, 'HNL', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (62, 'HKD', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (63, 'HUF', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (64, 'ISK', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (65, 'INR', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (66, 'IDR', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (67, 'IRR', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (68, 'IQD', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (69, 'ILS', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (70, 'JMD', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (71, 'JPY', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (72, 'JOD', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (73, 'KZT', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (74, 'KES', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (75, 'KRW', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (76, 'KWD', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (77, 'KGS', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (78, 'LAK', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (79, 'LVL', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (80, 'LBP', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (81, 'LSL', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (82, 'LRD', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (83, 'LYD', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (84, 'LTL', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (85, 'MOP', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (86, 'MKD', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (87, 'MGA', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (88, 'MWK', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (89, 'MYR', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (90, 'MVR', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (91, 'MRU', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (92, 'MUR', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (93, 'MXN', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (94, 'MDL', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (95, 'MNT', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (96, 'MAD', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (97, 'MZN', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (98, 'MMK', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (99, 'NAD', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (100, 'NPR', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (101, 'ANG', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (102, 'NZD', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (103, 'NIO', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (104, 'NGN', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (105, 'KPW', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (106, 'NOK', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (107, 'OMR', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (108, 'PKR', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (109, 'PAB', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (110, 'PGK', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (111, 'PYG', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (112, 'PEN', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (113, 'PHP', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (114, 'PLN', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (115, 'QAR', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (116, 'RON', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (117, 'RUB', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (118, 'RWF', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (119, 'SHP', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (120, 'WST', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (121, 'STN', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (122, 'SAR', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (123, 'RSD', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (124, 'SCR', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (125, 'SLL', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (126, 'SGD', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (127, 'SBD', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (128, 'SOS', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (129, 'ZAR', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (130, 'SSP', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (131, 'LKR', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (132, 'SDG', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (133, 'SRD', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (134, 'SZL', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (135, 'SEK', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (136, 'CHF', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (137, 'SYP', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (138, 'TWD', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (139, 'TJS', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (140, 'TZS', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (141, 'THB', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (142, 'TOP', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (143, 'TTD', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (144, 'TND', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (145, 'TRY', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (146, 'TMT', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (147, 'AED', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (148, 'UGX', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (149, 'UAH', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (150, 'GBP', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (151, 'UYU', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (152, 'USD', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (153, 'UZS', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (154, 'VUV', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (155, 'VES', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (156, 'VND', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (157, 'YER', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (158, 'ZMW', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (159, 'ZWL', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (160, 'XXX', 'NONE', 'date', 'DESC', NULL, NULL, NULL, NULL);

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (161, 'XAU', 'NONE', 'date', 'DESC', NULL, NULL, NULL, 'COMMODITY');

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (162, 'XPD', 'NONE', 'date', 'DESC', NULL, NULL, NULL, 'COMMODITY');

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (163, 'XPT', 'NONE', 'date', 'DESC', NULL, NULL, NULL, 'COMMODITY');

INSERT INTO "currency" ("_id", "code", "grouping", "sort_by", "sort_direction", "label", "fraction_digits", "symbol", "commodity_type") VALUES (164, 'XAG', 'NONE', 'date', 'DESC', NULL, NULL, NULL, 'COMMODITY');

INSERT INTO "account_types" ("_id", "label", "type_sort_key", "isAsset", "supportsReconciliation") VALUES (1, '_CASH_', 2, 1, 0);

INSERT INTO "account_types" ("_id", "label", "type_sort_key", "isAsset", "supportsReconciliation") VALUES (2, '_BANK_', 1, 1, 1);

INSERT INTO "account_types" ("_id", "label", "type_sort_key", "isAsset", "supportsReconciliation") VALUES (3, '_CCARD_', 0, 0, 1);

INSERT INTO "account_types" ("_id", "label", "type_sort_key", "isAsset", "supportsReconciliation") VALUES (4, '_ASSET_', -1, 1, 1);

INSERT INTO "account_types" ("_id", "label", "type_sort_key", "isAsset", "supportsReconciliation") VALUES (5, '_LIABILITY_', -1, 0, 1);

INSERT INTO "account_types" ("_id", "label", "type_sort_key", "isAsset", "supportsReconciliation") VALUES (6, '_INVST_', 0, 1, 1);

INSERT INTO "account_flags" ("_id", "flag_label", "flag_sort_key", "flag_icon", "visible") VALUES (0, '_DEFAULT_', 0, NULL, 1);

INSERT INTO "account_flags" ("_id", "flag_label", "flag_sort_key", "flag_icon", "visible") VALUES (1, '_FAVORITE_', 1, 'star', 1);

INSERT INTO "account_flags" ("_id", "flag_label", "flag_sort_key", "flag_icon", "visible") VALUES (2, '_INACTIVE_', -1, 'box-archive', 0);

INSERT INTO "paymentmethods" ("_id", "label", "is_numbered", "type", "icon") VALUES (0, '__NULL__', 0, 0, NULL);

INSERT INTO "paymentmethods" ("_id", "label", "is_numbered", "type", "icon") VALUES (1, 'CHEQUE', 1, -1, 'money-check');

INSERT INTO "paymentmethods" ("_id", "label", "is_numbered", "type", "icon") VALUES (2, 'CREDITCARD', 0, -1, 'credit-card');

INSERT INTO "paymentmethods" ("_id", "label", "is_numbered", "type", "icon") VALUES (3, 'DEPOSIT', 0, 1, 'down-long');

INSERT INTO "paymentmethods" ("_id", "label", "is_numbered", "type", "icon") VALUES (4, 'DIRECTDEBIT', 0, -1, 'up-long');

INSERT INTO "accounttype_paymentmethod" ("type", "method_id") VALUES (2, 1);

INSERT INTO "accounttype_paymentmethod" ("type", "method_id") VALUES (2, 2);

INSERT INTO "accounttype_paymentmethod" ("type", "method_id") VALUES (2, 3);

INSERT INTO "accounttype_paymentmethod" ("type", "method_id") VALUES (2, 4);

INSERT INTO "attributes" ("_id", "attribute_name", "context") VALUES (1, 'EREF', 'FinTS');

INSERT INTO "attributes" ("_id", "attribute_name", "context") VALUES (2, 'KREF', 'FinTS');

INSERT INTO "attributes" ("_id", "attribute_name", "context") VALUES (3, 'MREF', 'FinTS');

INSERT INTO "attributes" ("_id", "attribute_name", "context") VALUES (4, 'CRED', 'FinTS');

INSERT INTO "attributes" ("_id", "attribute_name", "context") VALUES (5, 'DBET', 'FinTS');

INSERT INTO "attributes" ("_id", "attribute_name", "context") VALUES (6, 'SALDO', 'FinTS');

INSERT INTO "attributes" ("_id", "attribute_name", "context") VALUES (7, 'CHECKSUM', 'FinTS');

INSERT INTO "attributes" ("_id", "attribute_name", "context") VALUES (8, 'NAME', 'Banking');

INSERT INTO "attributes" ("_id", "attribute_name", "context") VALUES (9, 'BLZ', 'Banking');

INSERT INTO "attributes" ("_id", "attribute_name", "context") VALUES (10, 'IBAN', 'Banking');

INSERT INTO "attributes" ("_id", "attribute_name", "context") VALUES (11, 'BIC', 'Banking');

INSERT INTO "attributes" ("_id", "attribute_name", "context") VALUES (12, 'NUMBER', 'Banking');

INSERT INTO "attributes" ("_id", "attribute_name", "context") VALUES (13, 'SUBNUMBER', 'Banking');

INSERT INTO "attributes" ("_id", "attribute_name", "context") VALUES (14, 'LAST_SYCNED_WITH_BANK', 'Banking');

INSERT INTO "attributes" ("_id", "attribute_name", "context") VALUES (15, 'GESCHAEFTS_VORFALL', 'Banking');

INSERT INTO "categories" ("_id", "label", "label_normalized", "parent_id", "usages", "last_used", "color", "icon", "uuid", "type") VALUES (0, '__SPLIT_TRANSACTION__', NULL, 0, 0, NULL, NULL, NULL, NULL, NULL);

INSERT INTO "categories" ("_id", "label", "label_normalized", "parent_id", "usages", "last_used", "color", "icon", "uuid", "type") VALUES (1, 'Transfer', NULL, NULL, 0, NULL, -13996670, NULL, '9d84b522-4c8c-40bd-a8f8-18c8788ee59e', 0);

INSERT INTO "payee" ("_id", "name", "short_name", "iban", "bic", "name_normalized", "parent_id") VALUES (0, '__NULL__', NULL, NULL, NULL, NULL, NULL);

INSERT INTO "android_metadata" ("locale") VALUES ('en_US');

CREATE UNIQUE INDEX accounts_uuid ON accounts(uuid);

CREATE INDEX budget_allocations_cat_id_index on budget_allocations(cat_id);

CREATE UNIQUE INDEX categories_label ON categories(label,coalesce(parent_id, 0));

CREATE UNIQUE INDEX categories_uuid ON categories(uuid);

CREATE UNIQUE INDEX payee_name ON payee(name) WHERE iban IS NULL;

CREATE INDEX templates_cat_id_index on templates(cat_id);

CREATE INDEX templates_payee_id_index on templates(payee_id);

CREATE UNIQUE INDEX transactions_account_uuid_index ON transactions(account_id,uuid,status);

CREATE INDEX transactions_cat_id_index on transactions(cat_id);

CREATE INDEX transactions_parent_id_index on transactions(parent_id);

CREATE INDEX transactions_payee_id_index on transactions(payee_id);

CREATE VIEW changes_extended AS  SELECT changes.*, payee.short_name, payee.name, paymentmethods.label AS method_label, paymentmethods.icon AS method_icon FROM changes LEFT JOIN payee ON payee_id = payee._id LEFT JOIN paymentmethods ON method_id = paymentmethods._id;

CREATE VIEW prioritized_prices AS SELECT
    p1.currency,
    p1.commodity,
    p1.date,
    p1.source,
    p1.value
FROM
    prices AS p1 WHERE
    p1.source = (
        SELECT p2.source
        FROM prices AS p2
        WHERE p2.currency = p1.currency AND p2.commodity = p1.commodity AND p2.date = p1.date
        ORDER BY CASE
            WHEN p2.source = 'user' THEN 1
            WHEN p2.source = 'calculation' THEN 3
            ELSE 2
        END,
        p2.source DESC
        LIMIT 1
    );

CREATE VIEW templates_all AS WITH Tree AS (
SELECT
    main.label AS path,
    icon,
    type,
    _id
FROM categories main
WHERE parent_id IS NULL
UNION ALL
SELECT
    Tree.path || ' > ' || subtree.label,
    subtree.icon,
    subtree.type,
    subtree._id
FROM categories subtree
JOIN Tree ON Tree._id = subtree.parent_id
) SELECT templates.*, payee.short_name, payee.name, paymentmethods.label AS method_label, paymentmethods.icon AS method_icon, Tree.path, Tree.icon, Tree.type, color, currency, sealed, exclude_from_totals, dynamic, is_portfolio, accounts.type AS account_type, accounts.label AS account_label, accounts.flag AS flag FROM templates LEFT JOIN payee ON payee_id = payee._id LEFT JOIN paymentmethods ON method_id = paymentmethods._id LEFT JOIN accounts ON account_id = accounts._id LEFT JOIN Tree ON cat_id = Tree._id;

CREATE VIEW templates_extended AS WITH Tree AS (
SELECT
    main.label AS path,
    icon,
    type,
    _id
FROM categories main
WHERE parent_id IS NULL
UNION ALL
SELECT
    Tree.path || ' > ' || subtree.label,
    subtree.icon,
    subtree.type,
    subtree._id
FROM categories subtree
JOIN Tree ON Tree._id = subtree.parent_id
) SELECT templates.*, payee.short_name, payee.name, paymentmethods.label AS method_label, paymentmethods.icon AS method_icon, Tree.path, Tree.icon, Tree.type, color, currency, sealed, exclude_from_totals, dynamic, is_portfolio, accounts.type AS account_type, accounts.label AS account_label, accounts.flag AS flag FROM templates LEFT JOIN payee ON payee_id = payee._id LEFT JOIN paymentmethods ON method_id = paymentmethods._id LEFT JOIN accounts ON account_id = accounts._id LEFT JOIN Tree ON cat_id = Tree._id WHERE status != 2;

CREATE VIEW transactions_committed AS WITH Tree AS (
SELECT
    main.label AS path,
    icon,
    type,
    _id
FROM categories main
WHERE parent_id IS NULL
UNION ALL
SELECT
    Tree.path || ' > ' || subtree.label,
    subtree.icon,
    subtree.type,
    subtree._id
FROM categories subtree
JOIN Tree ON Tree._id = subtree.parent_id
)  SELECT transactions.*, Tree.path, Tree.icon, Tree.type, payee.name, payee.short_name, paymentmethods.label AS method_label, paymentmethods.icon AS method_icon, group_concat(tag_id,'') AS tag_list, accounts.currency FROM transactions
 LEFT JOIN payee ON payee_id = payee._id
 LEFT JOIN paymentmethods ON method_id = paymentmethods._id
 LEFT JOIN accounts ON transactions.account_id = accounts._id
 LEFT JOIN Tree ON cat_id = TREE._id LEFT JOIN transactions_tags ON transactions_tags.transaction_id = transactions._id LEFT JOIN tags ON tag_id= tags._id WHERE status != 2 GROUP BY transactions._id;

CREATE VIEW transactions_extended AS WITH Tree AS (
SELECT
    main.label AS path,
    icon,
    type,
    _id
FROM categories main
WHERE parent_id IS NULL
UNION ALL
SELECT
    Tree.path || ' > ' || subtree.label,
    subtree.icon,
    subtree.type,
    subtree._id
FROM categories subtree
JOIN Tree ON Tree._id = subtree.parent_id
),cte_tags as (SELECT transaction_id, group_concat(tag_id,'') AS tag_list FROM transactions_tags  GROUP BY transaction_id),cte_attachments as (SELECT transaction_id, count(uri) AS attachment_count FROM transaction_attachments LEFT JOIN attachments ON attachment_id = attachments._id GROUP BY transaction_id) SELECT transactions.*, payee.short_name, payee.name, paymentmethods.label AS method_label, paymentmethods.icon AS method_icon, Tree.path, Tree.icon, Tree.type, color, currency, sealed, exclude_from_totals, dynamic, is_portfolio, accounts.type AS account_type, accounts.label AS account_label, accounts.flag AS flag, planinstance_transaction.template_id, tag_list, attachment_count, iban FROM transactions LEFT JOIN payee ON payee_id = payee._id LEFT JOIN paymentmethods ON method_id = paymentmethods._id LEFT JOIN accounts ON account_id = accounts._id LEFT JOIN Tree ON cat_id = Tree._id LEFT JOIN planinstance_transaction ON transactions._id = planinstance_transaction.transaction_id LEFT JOIN cte_tags ON cte_tags.transaction_id = transactions._id LEFT JOIN cte_attachments ON cte_attachments.transaction_id = transactions._id WHERE status != 2;

CREATE VIEW transactions_with_account AS SELECT transactions.*, categories.type, accounts.color, currency, exclude_from_totals, dynamic, accounts.type AS account_type, accounts.label AS account_label FROM transactions LEFT JOIN categories on cat_id = categories._id LEFT JOIN accounts ON account_id = accounts._id WHERE status != 2;

CREATE TRIGGER account_remap_transfer_transaction_update
AFTER UPDATE on transactions WHEN new.account_id != old.account_id
BEGIN
    UPDATE transactions SET transfer_account = new.account_id WHERE _id = new.transfer_peer;
END;

CREATE TRIGGER category_hierarchy_update
BEFORE UPDATE ON categories WHEN new.parent_id IS NOT old.parent_id AND new.parent_id IN (
WITH Tree AS (
SELECT
    _id,
    parent_id,
    1 AS level
FROM categories main
WHERE _id= new._id
UNION ALL
SELECT
    subtree._id,
    subtree.parent_id,
    level + 1
FROM categories subtree
JOIN Tree ON Tree._id = subtree.parent_id
ORDER BY level DESC
) SELECT _id From Tree
)
BEGIN SELECT RAISE (FAIL, 'attempt to create inconsistent category hierarchy'); END;

CREATE TRIGGER category_type_insert
    AFTER INSERT
    ON categories
    WHEN new.parent_id IS NOT NULL
    BEGIN
        UPDATE categories SET type = (SELECT type FROM categories WHERE _id = new.parent_id) WHERE _id = new._id;
    END;

CREATE TRIGGER category_type_move
    AFTER UPDATE
    ON categories
    WHEN new.parent_id IS NOT old.parent_id AND new.parent_id IS NOT NULL
    BEGIN
        UPDATE categories SET type = (SELECT type FROM categories WHERE _id = new.parent_id) WHERE _id = new._id;
    END;

CREATE TRIGGER category_type_update_type_main
    AFTER UPDATE
    ON categories
    WHEN new.type IS NOT old.type
    BEGIN
        UPDATE categories SET type = new.type WHERE parent_id = new._id;
    END;

CREATE TRIGGER category_type_update_type_sub
    BEFORE UPDATE
    ON categories
    WHEN new.type IS NOT old.type AND new.parent_id IS NOT NULL AND new.type IS NOT (SELECT type FROM categories WHERE _id = new.parent_id)
    BEGIN
        SELECT RAISE (ABORT, 'sub category type must match parent type');
    END;

CREATE TRIGGER delete_after_update_change_log AFTER UPDATE ON transactions WHEN 
        EXISTS (SELECT 1 FROM accounts WHERE _id = old.account_id AND sync_account_name IS NOT NULL AND sync_sequence_local > 0) AND NOT EXISTS (SELECT 1 FROM _sync_state) AND 
        old.account_id != new.account_id
         BEGIN
        INSERT INTO changes(type,sync_sequence_local, account_id,uuid,parent_uuid) 
        VALUES (
        'deleted',
        (SELECT sync_sequence_local FROM accounts WHERE _id = old.account_id),
        old.account_id,
        new.uuid,
        CASE
        WHEN old.parent_id IS NULL
        THEN NULL
        ELSE (
            SELECT uuid
            FROM transactions parent
            WHERE _id = old.parent_id
        )
       END);
        END;

CREATE TRIGGER delete_change_log AFTER DELETE ON transactions 
        WHEN EXISTS (SELECT 1 FROM accounts WHERE _id = old.account_id AND sync_account_name IS NOT NULL AND sync_sequence_local > 0) AND NOT EXISTS (SELECT 1 FROM _sync_state) AND
        EXISTS (SELECT 1 FROM accounts WHERE _id = old.account_id)
        BEGIN
        INSERT INTO changes(type,sync_sequence_local, account_id,uuid,parent_uuid) 
        VALUES (
        'deleted',
        (SELECT sync_sequence_local FROM accounts WHERE _id = old.account_id),
        old.account_id, old.uuid,
        CASE
        WHEN old.parent_id IS NULL
        THEN NULL
        ELSE (
            SELECT uuid
            FROM transactions parent
            WHERE _id = old.parent_id
        )
       END);
        END;

CREATE TRIGGER delete_change_log_attachments AFTER DELETE ON transaction_attachments
    WHEN EXISTS (SELECT 1 FROM accounts WHERE _id = (SELECT account_id FROM transactions WHERE _id = old.transaction_id) AND sync_account_name IS NOT NULL AND sync_sequence_local > 0) AND NOT EXISTS (SELECT 1 FROM _sync_state)
        BEGIN INSERT INTO changes (type, uuid, parent_uuid, account_id, sync_sequence_local)
        VALUES ('attachments', (SELECT uuid FROM transactions WHERE _id = old.transaction_id),
        CASE
        WHEN (SELECT parent_id FROM transactions WHERE _id = old.transaction_id) IS NULL
        THEN NULL
        ELSE (
            SELECT uuid
            FROM transactions parent
            WHERE _id = (SELECT parent_id FROM transactions WHERE _id = old.transaction_id)
        )
       END,
        (SELECT account_id FROM transactions WHERE _id = old.transaction_id), 
        (SELECT sync_sequence_local FROM accounts WHERE _id = (SELECT account_id FROM transactions WHERE _id = old.transaction_id))); END;

CREATE TRIGGER delete_change_log_tags AFTER DELETE ON transactions_tags
    WHEN EXISTS (SELECT 1 FROM accounts WHERE _id = (SELECT account_id FROM transactions WHERE _id = old.transaction_id) AND sync_account_name IS NOT NULL AND sync_sequence_local > 0) AND NOT EXISTS (SELECT 1 FROM _sync_state)
        BEGIN INSERT INTO changes (type, uuid, parent_uuid, account_id, sync_sequence_local)
        VALUES ('tags', (SELECT uuid FROM transactions WHERE _id = old.transaction_id),
        CASE
        WHEN (SELECT parent_id FROM transactions WHERE _id = old.transaction_id) IS NULL
        THEN NULL
        ELSE (
            SELECT uuid
            FROM transactions parent
            WHERE _id = (SELECT parent_id FROM transactions WHERE _id = old.transaction_id)
        )
       END,
        (SELECT account_id FROM transactions WHERE _id = old.transaction_id), 
        (SELECT sync_sequence_local FROM accounts WHERE _id = (SELECT account_id FROM transactions WHERE _id = old.transaction_id))); END;

CREATE TRIGGER delete_transfer_tags AFTER DELETE ON transactions_tags WHEN (SELECT transfer_peer FROM transactions WHERE _id = old.transaction_id) IS NOT NULL BEGIN DELETE FROM transactions_tags WHERE transaction_id = (SELECT transfer_peer FROM transactions WHERE _id = old.transaction_id); END;

CREATE TRIGGER insert_after_update_change_log AFTER UPDATE ON transactions
    WHEN EXISTS (SELECT 1 FROM accounts WHERE _id = new.account_id AND sync_account_name IS NOT NULL AND sync_sequence_local > 0) AND NOT EXISTS (SELECT 1 FROM _sync_state) AND
    old.account_id != new.account_id
    BEGIN
    INSERT INTO changes(type,sync_sequence_local, uuid, parent_uuid, comment, date, value_date, amount, original_amount, original_currency, cat_id, account_id, payee_id, transfer_account, method_id, cr_status, status, number)
        VALUES ('created',
        (SELECT sync_sequence_local FROM accounts WHERE _id = new.account_id),
        new.uuid,
        CASE
        WHEN new.parent_id IS NULL
        THEN NULL
        ELSE (
            SELECT uuid
            FROM transactions parent
            WHERE _id = new.parent_id
        )
       END,
        new.comment, new.date, new.value_date, new.amount, new.original_amount, new.original_currency, new.cat_id, new.account_id, new.payee_id, new.transfer_account, new.method_id, new.cr_status, new.status, new.number);
    END;

CREATE TRIGGER insert_change_log AFTER INSERT ON transactions
    WHEN EXISTS (SELECT 1 FROM accounts WHERE _id = new.account_id AND sync_account_name IS NOT NULL AND sync_sequence_local > 0) AND NOT EXISTS (SELECT 1 FROM _sync_state)
    BEGIN
    INSERT INTO changes(type,sync_sequence_local, uuid, parent_uuid, comment, date, value_date, amount, original_amount, original_currency, cat_id, account_id, payee_id, transfer_account, method_id, cr_status, status, number)
        VALUES ('created',
        (SELECT sync_sequence_local FROM accounts WHERE _id = new.account_id),
        new.uuid,
        CASE
        WHEN new.parent_id IS NULL
        THEN NULL
        ELSE (
            SELECT uuid
            FROM transactions parent
            WHERE _id = new.parent_id
        )
       END,
        new.comment, new.date, new.value_date, new.amount, new.original_amount, new.original_currency, new.cat_id, new.account_id, new.payee_id, new.transfer_account, new.method_id, new.cr_status, new.status, new.number);
    END;

CREATE TRIGGER insert_change_log_attachments AFTER INSERT ON transaction_attachments
    WHEN EXISTS (SELECT 1 FROM accounts WHERE _id = (SELECT account_id FROM transactions WHERE _id = new.transaction_id) AND sync_account_name IS NOT NULL AND sync_sequence_local > 0) AND NOT EXISTS (SELECT 1 FROM _sync_state)
        BEGIN INSERT INTO changes (type, uuid, parent_uuid, account_id, sync_sequence_local)
        VALUES ('attachments', (SELECT uuid FROM transactions WHERE _id = new.transaction_id),
        CASE
        WHEN (SELECT parent_id FROM transactions WHERE _id = new.transaction_id) IS NULL
        THEN NULL
        ELSE (
            SELECT uuid
            FROM transactions parent
            WHERE _id = (SELECT parent_id FROM transactions WHERE _id = new.transaction_id)
        )
       END,
        (SELECT account_id FROM transactions WHERE _id = new.transaction_id), 
        (SELECT sync_sequence_local FROM accounts WHERE _id = (SELECT account_id FROM transactions WHERE _id = new.transaction_id))); END;

CREATE TRIGGER insert_change_log_tags AFTER INSERT ON transactions_tags
    WHEN EXISTS (SELECT 1 FROM accounts WHERE _id = (SELECT account_id FROM transactions WHERE _id = new.transaction_id) AND sync_account_name IS NOT NULL AND sync_sequence_local > 0) AND NOT EXISTS (SELECT 1 FROM _sync_state)
        BEGIN INSERT INTO changes (type, uuid, parent_uuid, account_id, sync_sequence_local)
        VALUES ('tags', (SELECT uuid FROM transactions WHERE _id = new.transaction_id),
        CASE
        WHEN (SELECT parent_id FROM transactions WHERE _id = new.transaction_id) IS NULL
        THEN NULL
        ELSE (
            SELECT uuid
            FROM transactions parent
            WHERE _id = (SELECT parent_id FROM transactions WHERE _id = new.transaction_id)
        )
       END,
        (SELECT account_id FROM transactions WHERE _id = new.transaction_id), 
        (SELECT sync_sequence_local FROM accounts WHERE _id = (SELECT account_id FROM transactions WHERE _id = new.transaction_id))); END;

CREATE TRIGGER insert_equivalent_amount AFTER INSERT ON equivalent_amounts
    WHEN EXISTS (SELECT 1 FROM accounts WHERE _id = (SELECT account_id FROM transactions WHERE _id = new.transaction_id) AND sync_account_name IS NOT NULL AND sync_sequence_local > 0) AND NOT EXISTS (SELECT 1 FROM _sync_state)
        BEGIN INSERT INTO changes (type, uuid, account_id, equivalent_amount, sync_sequence_local, status)
        VALUES ('updated', (SELECT uuid FROM transactions WHERE _id = new.transaction_id),
        (SELECT account_id FROM transactions WHERE _id = new.transaction_id),
        new.equivalent_amount,
        (SELECT sync_sequence_local FROM accounts WHERE _id = (SELECT account_id FROM transactions WHERE _id = new.transaction_id)),
        null); END;

CREATE TRIGGER insert_increase_account_usage AFTER INSERT ON transactions WHEN new.parent_id IS NULL BEGIN UPDATE accounts SET usages = usages + 1, last_used = strftime('%s', 'now')  WHERE _id = new.account_id; END;

CREATE TRIGGER insert_increase_category_usage AFTER INSERT ON transactions WHEN new.cat_id IS NOT NULL AND new.cat_id != 0 BEGIN UPDATE categories SET usages = usages + 1, last_used = strftime('%s', 'now')  WHERE _id IN (new.cat_id , (SELECT parent_id FROM categories WHERE _id = new.cat_id)); END;

CREATE TRIGGER insert_transfer_tags AFTER INSERT ON transactions_tags WHEN (SELECT transfer_peer FROM transactions WHERE _id = new.transaction_id) IS NOT NULL BEGIN INSERT INTO transactions_tags (transaction_id, tag_id) VALUES ((SELECT transfer_peer FROM transactions WHERE _id = new.transaction_id), new.tag_id); END;

CREATE TRIGGER link_transfer_peer AFTER INSERT ON transactions WHEN new.transfer_peer IS NOT NULL
        BEGIN UPDATE transactions SET transfer_peer = new._id WHERE _id = new.transfer_peer;
        END;

CREATE TRIGGER party_hierarchy_update
AFTER UPDATE OF parent_id ON payee WHEN new.parent_id IS NOT NULL
BEGIN
UPDATE payee SET parent_id = new.parent_id WHERE parent_id = new._id;
END;

CREATE TRIGGER protect_default_flag BEFORE DELETE ON account_flags WHEN (OLD._id = 0) BEGIN SELECT RAISE (FAIL, 'default flag can not be deleted'); END;

CREATE TRIGGER protect_split_transaction   BEFORE DELETE   ON categories   WHEN (OLD._id = 0)   BEGIN   SELECT RAISE (FAIL, 'split category can not be deleted');    END;

CREATE TRIGGER sealed_account_tranfer_update
 BEFORE UPDATE OF comment, date, value_date, amount, cat_id, account_id, payee_id, transfer_peer, transfer_account, method_id, parent_id, number, uuid, original_amount, original_currency, debt_id
 ON transactions
 WHEN (SELECT sealed FROM accounts WHERE _id = old.transfer_account) = 1
 BEGIN SELECT RAISE (FAIL, 'attempt to update sealed account'); END;

CREATE TRIGGER sealed_account_transaction_delete
 BEFORE DELETE ON transactions
 WHEN (SELECT sealed FROM accounts WHERE _id = old.account_id) = 1
 BEGIN SELECT RAISE (FAIL, 'attempt to update sealed account'); END;

CREATE TRIGGER sealed_account_transaction_insert
 BEFORE INSERT ON transactions
 WHEN (SELECT sealed FROM accounts WHERE _id = new.account_id) = 1
 BEGIN SELECT RAISE (FAIL, 'attempt to update sealed account'); END;

CREATE TRIGGER sealed_account_transaction_update
 BEFORE UPDATE OF comment, date, value_date, amount, cat_id, account_id, payee_id, transfer_peer, transfer_account, method_id, parent_id, number, uuid, original_amount, original_currency, debt_id, cr_status
 ON transactions
 WHEN (SELECT max(sealed) FROM accounts WHERE _id IN (new.account_id,old.account_id)) = 1
 BEGIN SELECT RAISE (FAIL, 'attempt to update sealed account'); END;

CREATE TRIGGER sealed_account_update
 BEFORE UPDATE OF label,opening_balance,description,currency,type,uuid,criterion ON accounts
 WHEN old.sealed = 1
 BEGIN SELECT RAISE (FAIL, 'attempt to update sealed account'); END;

CREATE TRIGGER sealed_debt_transaction_delete
BEFORE DELETE ON transactions WHEN (SELECT sealed FROM debts WHERE _id = old.debt_id) = 1
BEGIN SELECT RAISE (FAIL, 'attempt to update sealed debt'); END;

CREATE TRIGGER sealed_debt_transaction_insert
BEFORE INSERT ON transactions WHEN (SELECT sealed FROM debts WHERE _id = new.debt_id) = 1
BEGIN SELECT RAISE (FAIL, 'attempt to update sealed debt'); END;

CREATE TRIGGER sealed_debt_transaction_update
BEFORE UPDATE ON transactions WHEN (SELECT max(sealed) FROM debts WHERE _id IN (new.debt_id,old.debt_id)) = 1
BEGIN SELECT RAISE (FAIL, 'attempt to update sealed debt'); END;

CREATE TRIGGER sealed_debt_update
BEFORE UPDATE OF date,label,amount,currency,description ON debts WHEN old.sealed = 1
BEGIN SELECT RAISE (FAIL, 'attempt to update sealed debt'); END;

CREATE TRIGGER sort_key_default AFTER INSERT ON accounts BEGIN UPDATE accounts SET sort_key = (SELECT coalesce(max(sort_key),0) FROM accounts) + 1 WHERE _id = NEW._id; END;

CREATE TRIGGER split_part_cr_status_trigger
 AFTER UPDATE OF cr_status ON transactions
 BEGIN UPDATE transactions SET cr_status = new.cr_status WHERE parent_id = new._id; END;

CREATE TRIGGER transaction_archive_trigger
        AFTER UPDATE ON transactions WHEN new.status != old.status AND new.status = 5
        BEGIN UPDATE transactions SET status = 5 WHERE parent_id = new._id; END;

CREATE TRIGGER transaction_unarchive_trigger
        AFTER UPDATE ON transactions WHEN new.status != old.status AND old.status = 5
        BEGIN UPDATE transactions SET status = new.status WHERE parent_id = new._id; END;

CREATE TRIGGER update_account_exchange_rate AFTER UPDATE ON account_exchangerates
    WHEN EXISTS (SELECT 1 FROM accounts WHERE _id = new.account_id AND sync_account_name IS NOT NULL AND sync_sequence_local > 0) AND NOT EXISTS (SELECT 1 FROM _sync_state)
    BEGIN INSERT INTO changes (type, uuid, account_id, sync_sequence_local)
    VALUES ('metadata', '_ignored_', new.account_id, (SELECT sync_sequence_local FROM accounts WHERE _id = old.account_id));
    END;

CREATE TRIGGER update_account_metadata AFTER UPDATE OF label,opening_balance,description,currency,type,color,exclude_from_totals,criterion ON accounts 
       WHEN new.sync_account_name IS NOT NULL AND new.sync_sequence_local > 0 AND NOT EXISTS (SELECT 1 FROM _sync_state)
       BEGIN INSERT INTO changes (type, uuid, account_id, sync_sequence_local) VALUES ('metadata', '_ignored_', new._id, new.sync_sequence_local); END;

CREATE TRIGGER update_account_sync_null AFTER UPDATE ON accounts WHEN new.sync_account_name IS NULL AND old.sync_account_name IS NOT NULL BEGIN UPDATE accounts SET sync_sequence_local = 0 WHERE _id = old._id; DELETE FROM changes WHERE account_id = old._id; END;

CREATE TRIGGER update_change_log AFTER UPDATE ON transactions WHEN 
        EXISTS (SELECT 1 FROM accounts WHERE _id = old.account_id AND sync_account_name IS NOT NULL AND sync_sequence_local > 0) AND NOT EXISTS (SELECT 1 FROM _sync_state) AND
        (new.status = old.status OR new.status = 5) AND
        new.account_id = old.account_id AND
        new.transfer_peer IS old.transfer_peer AND
        new.uuid IS NOT NULL
        BEGIN INSERT INTO changes(type,sync_sequence_local, uuid, account_id, parent_uuid, comment, date, value_date, amount, original_amount, original_currency, cat_id, payee_id, transfer_account, method_id, cr_status, status, number)
        VALUES ('updated', 
        (SELECT sync_sequence_local FROM accounts WHERE _id = old.account_id),
        new.uuid, 
        new.account_id,
        CASE
        WHEN new.parent_id IS NULL
        THEN NULL
        ELSE (
            SELECT uuid
            FROM transactions parent
            WHERE _id = new.parent_id
        )
       END,
        CASE WHEN old.comment = new.comment THEN NULL WHEN old.comment IS NOT NULL AND new.comment IS NULL THEN '' ELSE new.comment END, 
        CASE WHEN old.date = new.date THEN NULL ELSE new.date END,
        CASE WHEN old.value_date = new.value_date THEN NULL ELSE new.value_date END,
        CASE WHEN old.amount = new.amount THEN NULL ELSE new.amount END,
        CASE WHEN old.original_amount = new.original_amount THEN NULL WHEN old.original_amount IS NOT NULL AND new.original_amount IS NULL THEN -9223372036854775808 ELSE new.original_amount END,
        CASE WHEN old.original_currency = new.original_currency THEN NULL WHEN old.original_currency IS NOT NULL AND new.original_currency IS NULL THEN '' ELSE new.original_currency END,
        CASE WHEN old.cat_id = new.cat_id THEN NULL WHEN old.cat_id IS NOT NULL AND new.cat_id IS NULL THEN 0 ELSE new.cat_id END, 
        CASE WHEN old.payee_id = new.payee_id THEN NULL WHEN old.payee_id IS NOT NULL AND new.payee_id IS NULL THEN 0 ELSE new.payee_id END,
        CASE WHEN old.transfer_account = new.transfer_account THEN NULL WHEN old.transfer_account IS NOT NULL AND new.transfer_account IS NULL THEN -9223372036854775808 ELSE new.transfer_account END,
        CASE WHEN old.method_id = new.method_id THEN NULL WHEN old.method_id IS NOT NULL AND new.method_id IS NULL THEN 0 ELSE new.method_id END,
        CASE WHEN old.cr_status = new.cr_status THEN NULL ELSE new.cr_status END,
        CASE WHEN old.status = new.status THEN NULL ELSE new.status END,
        CASE WHEN old.number = new.number THEN NULL WHEN old.number IS NOT NULL AND new.number IS NULL THEN '' ELSE new.number END);
        END;

CREATE TRIGGER update_equivalent_amount AFTER UPDATE ON equivalent_amounts
    WHEN EXISTS (SELECT 1 FROM accounts WHERE _id = (SELECT account_id FROM transactions WHERE _id = old.transaction_id) AND sync_account_name IS NOT NULL AND sync_sequence_local > 0) AND NOT EXISTS (SELECT 1 FROM _sync_state)
            AND old.equivalent_amount != new.equivalent_amount
        BEGIN INSERT INTO changes (type, uuid, account_id, equivalent_amount, sync_sequence_local, status)
        VALUES ('updated', (SELECT uuid FROM transactions WHERE _id = old.transaction_id),
        (SELECT account_id FROM transactions WHERE _id = old.transaction_id),
        new.equivalent_amount,
        (SELECT sync_sequence_local FROM accounts WHERE _id = (SELECT account_id FROM transactions WHERE _id = old.transaction_id)),
        null); END;

CREATE TRIGGER update_increase_account_usage AFTER UPDATE ON transactions WHEN new.parent_id IS NULL AND new.account_id != old.account_id AND (old.transfer_account IS NULL OR new.account_id != old.transfer_account) BEGIN UPDATE accounts SET usages = usages + 1, last_used = strftime('%s', 'now')  WHERE _id = new.account_id; END;

CREATE TRIGGER update_increase_category_usage AFTER UPDATE ON transactions WHEN new.cat_id IS NOT NULL AND (old.cat_id IS NULL OR new.cat_id != old.cat_id) BEGIN UPDATE categories SET usages = usages + 1, last_used = strftime('%s', 'now')  WHERE _id IN (new.cat_id , (SELECT parent_id FROM categories WHERE _id = new.cat_id)); END;

CREATE TRIGGER uuid_update_change_log AFTER UPDATE ON transactions 
        WHEN EXISTS (SELECT 1 FROM accounts WHERE _id = new.account_id AND sync_account_name IS NOT NULL AND sync_sequence_local > 0) AND NOT EXISTS (SELECT 1 FROM _sync_state) 
        AND old.uuid != new.uuid
        BEGIN
        INSERT INTO changes(type,sync_sequence_local, uuid, parent_uuid, comment, date, value_date, amount, original_amount, original_currency, cat_id, account_id, payee_id, transfer_account, method_id, cr_status, status, number)
        VALUES ('created',
        (SELECT sync_sequence_local FROM accounts WHERE _id = new.account_id),
        new.uuid,
        CASE
        WHEN new.parent_id IS NULL
        THEN NULL
        ELSE (
            SELECT uuid
            FROM transactions parent
            WHERE _id = new.parent_id
        )
       END,
        new.comment, new.date, new.value_date, new.amount, new.original_amount, new.original_currency, new.cat_id, new.account_id, new.payee_id, new.transfer_account, new.method_id, new.cr_status, new.status, new.number);
        INSERT INTO changes(type,sync_sequence_local, account_id,uuid,parent_uuid) 
        VALUES (
        'deleted',
        (SELECT sync_sequence_local FROM accounts WHERE _id = old.account_id),
        old.account_id, old.uuid,
        CASE
        WHEN old.parent_id IS NULL
        THEN NULL
        ELSE (
            SELECT uuid
            FROM transactions parent
            WHERE _id = old.parent_id
        )
       END);
        END;

PRAGMA user_version=191;

COMMIT;
