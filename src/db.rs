/* db.rs
 *
 * Copyright 2026 nico359
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <https://www.gnu.org/licenses/>.
 *
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

use rusqlite::{params, Connection, Result};
use std::path::PathBuf;

#[derive(Debug, Clone)]
pub struct Account {
    pub id: i64,
    pub name: String,
    pub sort_order: i64,
}

#[derive(Debug, Clone)]
pub struct Expense {
    pub id: i64,
    pub account_id: i64,
    pub amount: f64,
    pub payee: String,
    pub note: String,
    pub date: String,
    pub is_income: bool,
    pub is_opening_balance: bool,
    pub recurring_id: Option<String>,
}

#[derive(Debug, Clone)]
pub struct RecurringExpense {
    pub id: String,
    pub account_id: i64,
    pub amount: f64,
    pub payee: String,
    pub note: String,
    pub is_income: bool,
    pub frequency: String,
    pub start_date: String,
    pub end_date: Option<String>,
    pub last_generated: String,
}

pub struct Database {
    conn: Connection,
}

impl std::fmt::Debug for Database {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("Database").finish()
    }
}

impl Database {
    pub fn new() -> Result<Self> {
        let db_path = Self::db_path();
        if let Some(parent) = db_path.parent() {
            std::fs::create_dir_all(parent).ok();
        }
        let conn = Connection::open(&db_path)?;
        let db = Self { conn };
        db.init()?;
        Ok(db)
    }

    pub fn db_path() -> PathBuf {
        let data_dir = glib::user_data_dir().join("expenses");
        data_dir.join("expenses.db")
    }

    fn init(&self) -> Result<()> {
        self.conn.execute_batch("PRAGMA journal_mode=WAL;")?;
        self.conn.execute_batch("PRAGMA foreign_keys=ON;")?;

        self.conn.execute_batch(
            "CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY,
                account_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                payee TEXT NOT NULL DEFAULT '',
                note TEXT NOT NULL DEFAULT '',
                date TEXT NOT NULL,
                is_income INTEGER NOT NULL DEFAULT 0,
                is_opening_balance INTEGER NOT NULL DEFAULT 0,
                recurring_id TEXT,
                FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_expenses_account ON expenses(account_id);
            CREATE INDEX IF NOT EXISTS idx_expenses_recurring ON expenses(recurring_id);

            CREATE TABLE IF NOT EXISTS recurring_expenses (
                id TEXT PRIMARY KEY,
                account_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                payee TEXT NOT NULL DEFAULT '',
                note TEXT NOT NULL DEFAULT '',
                is_income INTEGER NOT NULL DEFAULT 0,
                frequency TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT,
                last_generated TEXT NOT NULL,
                FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );"
        )?;

        // Ensure at least one account exists
        let count: i64 = self.conn.query_row(
            "SELECT COUNT(*) FROM accounts", [], |row| row.get(0)
        )?;
        if count == 0 {
            self.conn.execute(
                "INSERT INTO accounts (name, sort_order) VALUES ('Personal', 0)", []
            )?;
        }

        Ok(())
    }

    // --- Settings ---

    pub fn get_setting(&self, key: &str) -> Option<String> {
        self.conn.query_row(
            "SELECT value FROM settings WHERE key = ?1",
            params![key],
            |row| row.get(0),
        ).ok()
    }

    pub fn set_setting(&self, key: &str, value: &str) -> Result<()> {
        self.conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?1, ?2)",
            params![key, value],
        )?;
        Ok(())
    }

    // --- Accounts ---

    pub fn get_accounts(&self) -> Result<Vec<Account>> {
        let mut stmt = self.conn.prepare(
            "SELECT id, name, sort_order FROM accounts ORDER BY sort_order, name"
        )?;
        let accounts = stmt.query_map([], |row| {
            Ok(Account {
                id: row.get(0)?,
                name: row.get(1)?,
                sort_order: row.get(2)?,
            })
        })?.collect::<Result<Vec<_>>>()?;
        Ok(accounts)
    }

    pub fn get_account_by_name(&self, name: &str) -> Result<Option<Account>> {
        let result = self.conn.query_row(
            "SELECT id, name, sort_order FROM accounts WHERE name = ?1",
            params![name],
            |row| Ok(Account {
                id: row.get(0)?,
                name: row.get(1)?,
                sort_order: row.get(2)?,
            }),
        );
        match result {
            Ok(account) => Ok(Some(account)),
            Err(rusqlite::Error::QueryReturnedNoRows) => Ok(None),
            Err(e) => Err(e),
        }
    }

    pub fn add_account(&self, name: &str) -> Result<i64> {
        let max_order: i64 = self.conn.query_row(
            "SELECT COALESCE(MAX(sort_order), -1) FROM accounts", [], |row| row.get(0)
        )?;
        self.conn.execute(
            "INSERT INTO accounts (name, sort_order) VALUES (?1, ?2)",
            params![name, max_order + 1],
        )?;
        Ok(self.conn.last_insert_rowid())
    }

    pub fn delete_account(&self, account_id: i64) -> Result<()> {
        self.conn.execute("DELETE FROM accounts WHERE id = ?1", params![account_id])?;
        Ok(())
    }

    pub fn account_count(&self) -> Result<i64> {
        self.conn.query_row("SELECT COUNT(*) FROM accounts", [], |row| row.get(0))
    }

    // --- Expenses ---

    pub fn get_expenses(
        &self,
        account_id: i64,
        search: Option<&str>,
        limit: i64,
        offset: i64,
    ) -> Result<Vec<Expense>> {
        let (sql, search_param);
        if let Some(term) = search {
            search_param = format!("%{}%", term);
            sql = format!(
                "SELECT id, account_id, amount, payee, note, date, is_income, \
                 is_opening_balance, recurring_id \
                 FROM expenses WHERE account_id = ?1 \
                 AND (payee LIKE ?2 COLLATE NOCASE OR note LIKE ?2 COLLATE NOCASE) \
                 ORDER BY id DESC LIMIT ?3 OFFSET ?4"
            );
            let mut stmt = self.conn.prepare(&sql)?;
            let expenses = stmt.query_map(
                params![account_id, search_param, limit, offset],
                Self::row_to_expense,
            )?.collect::<Result<Vec<_>>>()?;
            Ok(expenses)
        } else {
            sql = "SELECT id, account_id, amount, payee, note, date, is_income, \
                   is_opening_balance, recurring_id \
                   FROM expenses WHERE account_id = ?1 \
                   ORDER BY id DESC LIMIT ?2 OFFSET ?3".to_string();
            let mut stmt = self.conn.prepare(&sql)?;
            let expenses = stmt.query_map(
                params![account_id, limit, offset],
                Self::row_to_expense,
            )?.collect::<Result<Vec<_>>>()?;
            Ok(expenses)
        }
    }

    pub fn get_expense_count(&self, account_id: i64, search: Option<&str>) -> Result<i64> {
        if let Some(term) = search {
            let search_param = format!("%{}%", term);
            self.conn.query_row(
                "SELECT COUNT(*) FROM expenses WHERE account_id = ?1 \
                 AND (payee LIKE ?2 COLLATE NOCASE OR note LIKE ?2 COLLATE NOCASE)",
                params![account_id, search_param],
                |row| row.get(0),
            )
        } else {
            self.conn.query_row(
                "SELECT COUNT(*) FROM expenses WHERE account_id = ?1",
                params![account_id],
                |row| row.get(0),
            )
        }
    }

    pub fn add_expense(
        &self,
        account_id: i64,
        amount: f64,
        payee: &str,
        note: &str,
        date: &str,
        is_income: bool,
        is_opening_balance: bool,
        recurring_id: Option<&str>,
    ) -> Result<i64> {
        self.conn.execute(
            "INSERT INTO expenses (account_id, amount, payee, note, date, is_income, \
             is_opening_balance, recurring_id) \
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)",
            params![account_id, amount, payee, note, date, is_income, is_opening_balance, recurring_id],
        )?;
        Ok(self.conn.last_insert_rowid())
    }

    pub fn delete_expense(&self, expense_id: i64) -> Result<()> {
        self.conn.execute("DELETE FROM expenses WHERE id = ?1", params![expense_id])?;
        Ok(())
    }

    pub fn get_balance(&self, account_id: i64) -> Result<f64> {
        let income: f64 = self.conn.query_row(
            "SELECT COALESCE(SUM(amount), 0) FROM expenses \
             WHERE account_id = ?1 AND is_income = 1",
            params![account_id],
            |row| row.get(0),
        )?;
        let expenses: f64 = self.conn.query_row(
            "SELECT COALESCE(SUM(amount), 0) FROM expenses \
             WHERE account_id = ?1 AND is_income = 0",
            params![account_id],
            |row| row.get(0),
        )?;
        Ok(income - expenses)
    }

    pub fn get_all_payees(&self, account_id: i64) -> Result<Vec<String>> {
        let mut stmt = self.conn.prepare(
            "SELECT DISTINCT payee FROM expenses WHERE account_id = ?1 \
             AND payee != '' ORDER BY payee COLLATE NOCASE"
        )?;
        let payees = stmt.query_map(params![account_id], |row| row.get(0))?
            .collect::<Result<Vec<_>>>()?;
        Ok(payees)
    }

    pub fn expense_exists_on_date(
        &self,
        account_id: i64,
        recurring_id: &str,
        date: &str,
    ) -> Result<bool> {
        let count: i64 = self.conn.query_row(
            "SELECT COUNT(*) FROM expenses \
             WHERE account_id = ?1 AND recurring_id = ?2 AND date LIKE ?3",
            params![account_id, recurring_id, format!("{}%", date)],
            |row| row.get(0),
        )?;
        Ok(count > 0)
    }

    // --- Recurring Expenses ---

    pub fn get_recurring_expenses(&self) -> Result<Vec<RecurringExpense>> {
        let mut stmt = self.conn.prepare(
            "SELECT id, account_id, amount, payee, note, is_income, frequency, \
             start_date, end_date, last_generated FROM recurring_expenses"
        )?;
        let recurring = stmt.query_map([], |row| {
            Ok(RecurringExpense {
                id: row.get(0)?,
                account_id: row.get(1)?,
                amount: row.get(2)?,
                payee: row.get(3)?,
                note: row.get(4)?,
                is_income: row.get::<_, i64>(5)? != 0,
                frequency: row.get(6)?,
                start_date: row.get(7)?,
                end_date: row.get(8)?,
                last_generated: row.get(9)?,
            })
        })?.collect::<Result<Vec<_>>>()?;
        Ok(recurring)
    }

    pub fn get_recurring_expense(&self, id: &str) -> Result<Option<RecurringExpense>> {
        let result = self.conn.query_row(
            "SELECT id, account_id, amount, payee, note, is_income, frequency, \
             start_date, end_date, last_generated FROM recurring_expenses WHERE id = ?1",
            params![id],
            |row| Ok(RecurringExpense {
                id: row.get(0)?,
                account_id: row.get(1)?,
                amount: row.get(2)?,
                payee: row.get(3)?,
                note: row.get(4)?,
                is_income: row.get::<_, i64>(5)? != 0,
                frequency: row.get(6)?,
                start_date: row.get(7)?,
                end_date: row.get(8)?,
                last_generated: row.get(9)?,
            }),
        );
        match result {
            Ok(r) => Ok(Some(r)),
            Err(rusqlite::Error::QueryReturnedNoRows) => Ok(None),
            Err(e) => Err(e),
        }
    }

    pub fn add_recurring_expense(
        &self,
        id: &str,
        account_id: i64,
        amount: f64,
        payee: &str,
        note: &str,
        is_income: bool,
        frequency: &str,
        start_date: &str,
        end_date: Option<&str>,
        last_generated: &str,
    ) -> Result<()> {
        self.conn.execute(
            "INSERT INTO recurring_expenses \
             (id, account_id, amount, payee, note, is_income, frequency, \
              start_date, end_date, last_generated) \
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10)",
            params![id, account_id, amount, payee, note, is_income, frequency,
                    start_date, end_date, last_generated],
        )?;
        Ok(())
    }

    pub fn update_recurring_last_generated(&self, id: &str, last_generated: &str) -> Result<()> {
        self.conn.execute(
            "UPDATE recurring_expenses SET last_generated = ?1 WHERE id = ?2",
            params![last_generated, id],
        )?;
        Ok(())
    }

    pub fn update_recurring_frequency(
        &self,
        id: &str,
        frequency: &str,
        end_date: Option<&str>,
    ) -> Result<()> {
        self.conn.execute(
            "UPDATE recurring_expenses SET frequency = ?1, end_date = ?2 WHERE id = ?3",
            params![frequency, end_date, id],
        )?;
        Ok(())
    }

    pub fn delete_recurring_expense(&self, id: &str) -> Result<()> {
        self.conn.execute("DELETE FROM recurring_expenses WHERE id = ?1", params![id])?;
        self.conn.execute(
            "UPDATE expenses SET recurring_id = NULL WHERE recurring_id = ?1",
            params![id],
        )?;
        Ok(())
    }

    // --- Import/Export helpers ---

    pub fn replace_all_data(
        &self,
        accounts: &[(String, i64)],
        expenses: &[(i64, f64, String, String, String, bool, bool)],
    ) -> Result<()> {
        let tx = self.conn.unchecked_transaction()?;
        tx.execute_batch("DELETE FROM recurring_expenses; DELETE FROM expenses; DELETE FROM accounts;")?;
        for (i, (name, sort_order)) in accounts.iter().enumerate() {
            tx.execute(
                "INSERT INTO accounts (id, name, sort_order) VALUES (?1, ?2, ?3)",
                params![i as i64 + 1, name, sort_order],
            )?;
        }
        for (account_id, amount, payee, note, date, is_income, is_opening_balance) in expenses {
            tx.execute(
                "INSERT INTO expenses (account_id, amount, payee, note, date, is_income, is_opening_balance) \
                 VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)",
                params![account_id, amount, payee, note, date, is_income, is_opening_balance],
            )?;
        }
        tx.commit()?;
        Ok(())
    }

    pub fn get_all_expenses_for_export(&self) -> Result<Vec<Expense>> {
        let mut stmt = self.conn.prepare(
            "SELECT id, account_id, amount, payee, note, date, is_income, \
             is_opening_balance, recurring_id FROM expenses ORDER BY id"
        )?;
        let expenses = stmt.query_map([], Self::row_to_expense)?
            .collect::<Result<Vec<_>>>()?;
        Ok(expenses)
    }

    pub fn connection(&self) -> &Connection {
        &self.conn
    }

    fn row_to_expense(row: &rusqlite::Row) -> Result<Expense> {
        Ok(Expense {
            id: row.get(0)?,
            account_id: row.get(1)?,
            amount: row.get(2)?,
            payee: row.get(3)?,
            note: row.get(4)?,
            date: row.get(5)?,
            is_income: row.get::<_, i64>(6)? != 0,
            is_opening_balance: row.get::<_, i64>(7)? != 0,
            recurring_id: row.get(8)?,
        })
    }
}

use gtk::glib;
