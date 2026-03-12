# db.py
#
# Copyright 2026 Unknown
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import sqlite3
import os


class Database:
    """SQLite database backend for expenses storage.

    Replaces the previous JSON-file approach with targeted SQL operations
    so that individual adds/edits/deletes are O(1) regardless of total
    transaction count.
    """

    def __init__(self, db_path):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                sort_order INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                payee TEXT NOT NULL,
                note TEXT DEFAULT '',
                date TEXT NOT NULL,
                is_income INTEGER DEFAULT 0,
                is_opening_balance INTEGER DEFAULT 0,
                recurring_id TEXT,
                FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS recurring_expenses (
                id TEXT PRIMARY KEY,
                account_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                payee TEXT NOT NULL,
                note TEXT DEFAULT '',
                is_income INTEGER DEFAULT 0,
                frequency TEXT NOT NULL DEFAULT 'monthly',
                start_date TEXT NOT NULL,
                end_date TEXT,
                last_generated TEXT,
                FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_expenses_account
                ON expenses(account_id);
            CREATE INDEX IF NOT EXISTS idx_expenses_recurring
                ON expenses(recurring_id);
        """)
        self.conn.commit()

    def close(self):
        if self.conn:
            self.conn.close()

    # ── Account operations ─────────────────────────────────────────────

    def get_accounts(self):
        """Return list of account names in sort order."""
        rows = self.conn.execute(
            "SELECT name FROM accounts ORDER BY sort_order, id"
        ).fetchall()
        return [r['name'] for r in rows]

    def _get_account_id(self, name):
        row = self.conn.execute(
            "SELECT id FROM accounts WHERE name = ?", (name,)
        ).fetchone()
        return row['id'] if row else None

    def add_account(self, name):
        """Add a new account. Returns the account id."""
        cursor = self.conn.execute(
            "INSERT INTO accounts (name) VALUES (?)", (name,)
        )
        self.conn.commit()
        return cursor.lastrowid

    def delete_account(self, name):
        """Delete an account and cascade-delete its expenses."""
        self.conn.execute("DELETE FROM accounts WHERE name = ?", (name,))
        self.conn.commit()

    def ensure_account(self, name):
        """Return the id for *name*, creating the account if needed."""
        aid = self._get_account_id(name)
        if aid is None:
            aid = self.add_account(name)
        return aid

    # ── Settings ───────────────────────────────────────────────────────

    def get_setting(self, key, default=None):
        row = self.conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        return row['value'] if row else default

    def set_setting(self, key, value):
        self.conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, str(value))
        )
        self.conn.commit()

    # ── Expense operations ─────────────────────────────────────────────

    def get_expenses(self, account_name, *, limit=None, offset=0, search=None):
        """Return expenses for *account_name* as a list of dicts.

        Results are ordered newest-first (descending id).

        Parameters
        ----------
        limit : int or None
            Maximum number of rows to return.  ``None`` means all.
        offset : int
            Number of rows to skip (for pagination).
        search : str or None
            If given, only return expenses whose payee or note contains
            this substring (case-insensitive).
        """
        account_id = self._get_account_id(account_name)
        if account_id is None:
            return []

        sql = """
            SELECT id, amount, payee, note, date, is_income,
                   is_opening_balance, recurring_id
            FROM expenses
            WHERE account_id = ?
        """
        params = [account_id]

        if search:
            sql += " AND (payee LIKE ? COLLATE NOCASE OR note LIKE ? COLLATE NOCASE)"
            like = f"%{search}%"
            params += [like, like]

        sql += " ORDER BY id DESC"

        if limit is not None:
            sql += " LIMIT ? OFFSET ?"
            params += [limit, offset]

        rows = self.conn.execute(sql, params).fetchall()

        results = []
        for r in rows:
            d = dict(r)
            d['is_income'] = bool(d['is_income'])
            d['is_opening_balance'] = bool(d['is_opening_balance'])
            results.append(d)
        return results

    def count_expenses(self, account_name, *, search=None):
        """Return the total number of expenses for *account_name*."""
        account_id = self._get_account_id(account_name)
        if account_id is None:
            return 0

        sql = "SELECT COUNT(*) AS cnt FROM expenses WHERE account_id = ?"
        params = [account_id]

        if search:
            sql += " AND (payee LIKE ? COLLATE NOCASE OR note LIKE ? COLLATE NOCASE)"
            like = f"%{search}%"
            params += [like, like]

        return self.conn.execute(sql, params).fetchone()['cnt']

    def get_expense_by_id(self, expense_id):
        """Return a single expense dict or None."""
        row = self.conn.execute("""
            SELECT id, amount, payee, note, date, is_income,
                   is_opening_balance, recurring_id
            FROM expenses WHERE id = ?
        """, (expense_id,)).fetchone()
        if row is None:
            return None
        d = dict(row)
        d['is_income'] = bool(d['is_income'])
        d['is_opening_balance'] = bool(d['is_opening_balance'])
        return d

    def add_expense(self, account_name, expense):
        """Insert a single expense. Returns the new row id."""
        account_id = self.ensure_account(account_name)
        cursor = self.conn.execute("""
            INSERT INTO expenses
                (account_id, amount, payee, note, date,
                 is_income, is_opening_balance, recurring_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            account_id,
            expense['amount'],
            expense['payee'],
            expense.get('note', ''),
            expense['date'],
            1 if expense.get('is_income', False) else 0,
            1 if expense.get('is_opening_balance', False) else 0,
            expense.get('recurring_id'),
        ))
        self.conn.commit()
        return cursor.lastrowid

    def delete_expense(self, expense_id):
        self.conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
        self.conn.commit()

    def set_expense_recurring(self, expense_id, recurring_id):
        self.conn.execute(
            "UPDATE expenses SET recurring_id = ? WHERE id = ?",
            (recurring_id, expense_id)
        )
        self.conn.commit()

    def clear_recurring_from_expenses(self, recurring_id):
        """Remove *recurring_id* from every expense that references it."""
        self.conn.execute(
            "UPDATE expenses SET recurring_id = NULL WHERE recurring_id = ?",
            (recurring_id,)
        )
        self.conn.commit()

    def get_account_total(self, account_name):
        account_id = self._get_account_id(account_name)
        if account_id is None:
            return 0.0
        row = self.conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total "
            "FROM expenses WHERE account_id = ?",
            (account_id,)
        ).fetchone()
        return row['total']

    # ── Recurring expense operations ───────────────────────────────────

    def get_recurring_expenses(self):
        """Return all recurring definitions with their account name."""
        rows = self.conn.execute("""
            SELECT r.id, r.amount, r.payee, r.note, r.is_income,
                   r.frequency, r.start_date, r.end_date, r.last_generated,
                   a.name AS account
            FROM recurring_expenses r
            JOIN accounts a ON r.account_id = a.id
        """).fetchall()

        results = []
        for r in rows:
            d = dict(r)
            d['is_income'] = bool(d['is_income'])
            results.append(d)
        return results

    def get_recurring_by_id(self, recurring_id):
        row = self.conn.execute("""
            SELECT r.id, r.amount, r.payee, r.note, r.is_income,
                   r.frequency, r.start_date, r.end_date, r.last_generated,
                   a.name AS account
            FROM recurring_expenses r
            JOIN accounts a ON r.account_id = a.id
            WHERE r.id = ?
        """, (recurring_id,)).fetchone()
        if row is None:
            return None
        d = dict(row)
        d['is_income'] = bool(d['is_income'])
        return d

    def add_recurring(self, account_name, recurring):
        account_id = self.ensure_account(account_name)
        self.conn.execute("""
            INSERT INTO recurring_expenses
                (id, account_id, amount, payee, note, is_income,
                 frequency, start_date, end_date, last_generated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            recurring['id'],
            account_id,
            recurring['amount'],
            recurring['payee'],
            recurring.get('note', ''),
            1 if recurring.get('is_income', False) else 0,
            recurring.get('frequency', 'monthly'),
            recurring['start_date'],
            recurring.get('end_date'),
            recurring.get('last_generated'),
        ))
        self.conn.commit()

    def delete_recurring(self, recurring_id):
        self.conn.execute(
            "DELETE FROM recurring_expenses WHERE id = ?", (recurring_id,)
        )
        self.conn.commit()

    _RECURRING_FIELDS = frozenset({
        'frequency', 'end_date', 'last_generated',
        'amount', 'payee', 'note', 'is_income', 'start_date',
    })

    def update_recurring(self, recurring_id, **fields):
        if not fields:
            return
        invalid = set(fields.keys()) - self._RECURRING_FIELDS
        if invalid:
            raise ValueError(f"Invalid field names: {invalid}")
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [recurring_id]
        self.conn.execute(
            f"UPDATE recurring_expenses SET {set_clause} WHERE id = ?",
            values
        )
        self.conn.commit()

    def expense_exists_on_date(self, account_name, target_date_str, payee, amount):
        """Check whether an expense already exists on a given date for
        the same payee and amount (used by recurring-expense generation)."""
        account_id = self._get_account_id(account_name)
        if account_id is None:
            return False
        row = self.conn.execute("""
            SELECT 1 FROM expenses
            WHERE account_id = ? AND payee = ? AND amount = ?
              AND date LIKE ? || '%'
            LIMIT 1
        """, (account_id, payee, amount, target_date_str)).fetchone()
        return row is not None

    # ── Payee helpers ──────────────────────────────────────────────────

    def get_all_payees(self):
        """Return sorted list of unique payee names across all accounts."""
        rows = self.conn.execute(
            "SELECT DISTINCT payee FROM expenses ORDER BY payee"
        ).fetchall()
        return [r['payee'] for r in rows]

    # ── Bulk operations (import / export) ──────────────────────────────

    def replace_all_data(self, data):
        """Clear the database and bulk-insert from a JSON-format dict."""
        self.conn.execute("DELETE FROM expenses")
        self.conn.execute("DELETE FROM recurring_expenses")
        self.conn.execute("DELETE FROM accounts")
        self.conn.execute("DELETE FROM settings")

        accounts = data.get('accounts', ['Default'])
        current_account = data.get(
            'current_account', accounts[0] if accounts else 'Default')
        expenses_data = data.get('expenses', {})
        recurring = data.get('recurring_expenses', [])

        # Insert accounts
        account_ids = {}
        for i, name in enumerate(accounts):
            cursor = self.conn.execute(
                "INSERT INTO accounts (name, sort_order) VALUES (?, ?)",
                (name, i)
            )
            account_ids[name] = cursor.lastrowid

        # Ensure every expense-key account exists
        for acct in expenses_data:
            if acct not in account_ids:
                cursor = self.conn.execute(
                    "INSERT INTO accounts (name) VALUES (?)", (acct,)
                )
                account_ids[acct] = cursor.lastrowid

        # Insert expenses
        for acct, expense_list in expenses_data.items():
            aid = account_ids[acct]
            for exp in expense_list:
                self.conn.execute("""
                    INSERT INTO expenses
                        (account_id, amount, payee, note, date,
                         is_income, is_opening_balance, recurring_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    aid,
                    exp['amount'],
                    exp['payee'],
                    exp.get('note', ''),
                    exp['date'],
                    1 if exp.get('is_income', False) else 0,
                    1 if exp.get('is_opening_balance', False) else 0,
                    exp.get('recurring_id'),
                ))

        # Insert recurring definitions
        for rec in recurring:
            acct = rec.get('account', current_account)
            aid = account_ids.get(acct)
            if aid is None:
                cursor = self.conn.execute(
                    "INSERT INTO accounts (name) VALUES (?)", (acct,)
                )
                aid = cursor.lastrowid
                account_ids[acct] = aid

            self.conn.execute("""
                INSERT INTO recurring_expenses
                    (id, account_id, amount, payee, note, is_income,
                     frequency, start_date, end_date, last_generated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                rec['id'],
                aid,
                rec['amount'],
                rec['payee'],
                rec.get('note', ''),
                1 if rec.get('is_income', False) else 0,
                rec.get('frequency', 'monthly'),
                rec['start_date'],
                rec.get('end_date'),
                rec.get('last_generated'),
            ))

        self.conn.execute(
            "INSERT INTO settings (key, value) VALUES ('current_account', ?)",
            (current_account,)
        )
        self.conn.commit()


