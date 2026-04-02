/* import_export.rs
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

use gtk::prelude::*;
use adw::prelude::*;
use gtk::{gio, glib};
use rusqlite::{params, Connection};

use std::io::{Read, Write};
use std::path::Path;

use crate::db::Database;
use crate::window::ExpensesWindow;

impl ExpensesWindow {
    // --- Import from MyExpenses ---

    pub(crate) fn on_import_myexpenses(&self) {
        let dialog = gtk::FileDialog::builder()
            .title("Import from MyExpenses")
            .build();

        let filter = gtk::FileFilter::new();
        filter.add_pattern("*.zip");
        filter.add_pattern("BACKUP");
        filter.set_name(Some("MyExpenses backup (ZIP or BACKUP)"));
        let filters = gio::ListStore::new::<gtk::FileFilter>();
        filters.append(&filter);
        dialog.set_filters(Some(&filters));

        dialog.open(Some(self), None::<&gio::Cancellable>, glib::clone!(
            #[weak(rename_to = window)]
            self,
            move |result| {
                if let Ok(file) = result {
                    if let Some(path) = file.path() {
                        window.do_import_myexpenses(&path);
                    }
                }
            }
        ));
    }

    fn do_import_myexpenses(&self, path: &Path) {
        let path_str = path.to_string_lossy();

        let backup_path = if path_str.ends_with(".zip") {
            match Self::extract_backup_from_zip(path) {
                Ok(p) => p,
                Err(e) => {
                    self.show_error("Import Failed", &format!("Could not extract ZIP: {}", e));
                    return;
                }
            }
        } else {
            path.to_path_buf()
        };

        match self.import_myexpenses_db(&backup_path) {
            Ok((accounts, expenses)) => {
                self.db().replace_all_data(&accounts, &expenses).ok();
                self.setup_accounts();
                self.refresh_expenses();
                self.show_info("Import Complete", "MyExpenses data imported successfully.");
            }
            Err(e) => {
                self.show_error("Import Failed", &format!("Could not read database: {}", e));
            }
        }

        // Clean up temp file if we extracted from zip
        if path_str.ends_with(".zip") {
            std::fs::remove_file(&backup_path).ok();
        }
    }

    fn extract_backup_from_zip(zip_path: &Path) -> Result<std::path::PathBuf, String> {
        let file = std::fs::File::open(zip_path).map_err(|e| e.to_string())?;
        let mut archive = zip::ZipArchive::new(file).map_err(|e| e.to_string())?;

        for i in 0..archive.len() {
            let mut entry = archive.by_index(i).map_err(|e| e.to_string())?;
            let name = entry.name().to_string();
            if name == "BACKUP" || name.ends_with("/BACKUP") {
                let tmp_dir = std::env::temp_dir();
                let tmp_path = tmp_dir.join("expenses-import-BACKUP");
                let mut outfile = std::fs::File::create(&tmp_path).map_err(|e| e.to_string())?;
                let mut buf = Vec::new();
                entry.read_to_end(&mut buf).map_err(|e| e.to_string())?;
                outfile.write_all(&buf).map_err(|e| e.to_string())?;
                return Ok(tmp_path);
            }
        }
        Err("No BACKUP file found in ZIP archive".to_string())
    }

    fn import_myexpenses_db(
        &self,
        db_path: &Path,
    ) -> Result<(Vec<(String, i64)>, Vec<(i64, f64, String, String, String, bool, bool)>), String> {
        let conn = Connection::open(db_path).map_err(|e| e.to_string())?;

        // Read accounts
        let mut stmt = conn.prepare(
            "SELECT _id, label, opening_balance FROM accounts ORDER BY sort_key ASC"
        ).map_err(|e| e.to_string())?;

        let accounts_raw: Vec<(i64, String, i64)> = stmt.query_map([], |row| {
            Ok((row.get(0)?, row.get(1)?, row.get(2)?))
        }).map_err(|e| e.to_string())?
          .filter_map(|r| r.ok())
          .collect();

        let mut accounts = Vec::new();
        let mut account_id_map = std::collections::HashMap::new();
        let mut expenses = Vec::new();

        for (i, (old_id, name, opening_balance_cents)) in accounts_raw.iter().enumerate() {
            let new_id = (i + 1) as i64;
            account_id_map.insert(*old_id, new_id);
            accounts.push((name.clone(), i as i64));

            // Add opening balance as special transaction
            if *opening_balance_cents > 0 {
                let amount = *opening_balance_cents as f64 / 100.0;
                expenses.push((
                    new_id,
                    amount,
                    "Opening Balance".to_string(),
                    "Initial balance imported from database".to_string(),
                    "0000-01-01 00:00".to_string(),
                    true,  // is_income
                    true,  // is_opening_balance
                ));
            }
        }

        // Read transactions
        let mut stmt = conn.prepare(
            "SELECT t.account_id, t.amount, t.date, t.comment, p.name \
             FROM transactions t \
             LEFT JOIN payee p ON t.payee_id = p._id \
             WHERE t.parent_id IS NULL \
             ORDER BY t.date ASC"
        ).map_err(|e| e.to_string())?;

        let transactions: Vec<(i64, i64, i64, Option<String>, Option<String>)> = stmt.query_map([], |row| {
            Ok((
                row.get(0)?,
                row.get(1)?,
                row.get(2)?,
                row.get(3)?,
                row.get(4)?,
            ))
        }).map_err(|e| e.to_string())?
          .filter_map(|r| r.ok())
          .collect();

        for (old_account_id, amount_cents, timestamp, comment, payee_name) in &transactions {
            let new_account_id = match account_id_map.get(old_account_id) {
                Some(id) => *id,
                None => continue,
            };

            let amount_euros = (*amount_cents as f64 / 100.0).abs();
            let is_income = *amount_cents > 0;

            let date_str = match chrono::DateTime::from_timestamp(*timestamp, 0) {
                Some(dt) => dt.with_timezone(&chrono::Local).format("%Y-%m-%d %H:%M").to_string(),
                None => chrono::Local::now().format("%Y-%m-%d %H:%M").to_string(),
            };

            let payee = payee_name.as_deref().unwrap_or("").trim().to_string();
            let note = comment.as_deref().unwrap_or("").to_string();

            expenses.push((
                new_account_id,
                amount_euros,
                payee,
                note,
                date_str,
                is_income,
                false, // is_opening_balance
            ));
        }

        Ok((accounts, expenses))
    }

    // --- Export for MyExpenses ---

    pub(crate) fn on_export_myexpenses(&self) {
        let timestamp = chrono::Local::now().format("%Y-%m-%d_%H-%M-%S");
        let dialog = gtk::FileDialog::builder()
            .title("Export for MyExpenses")
            .initial_name(format!("myexpenses-export-{}.zip", timestamp))
            .build();

        dialog.save(Some(self), None::<&gio::Cancellable>, glib::clone!(
            #[weak(rename_to = window)]
            self,
            move |result| {
                if let Ok(file) = result {
                    if let Some(path) = file.path() {
                        window.do_export_myexpenses(&path);
                    }
                }
            }
        ));
    }

    fn do_export_myexpenses(&self, zip_path: &Path) {
        let schema_bytes = gio::resources_lookup_data(
            "/io/github/nico359/expenses/myexpenses_schema.sql",
            gio::ResourceLookupFlags::NONE,
        );

        let schema_sql = match schema_bytes {
            Ok(bytes) => String::from_utf8_lossy(&bytes).to_string(),
            Err(e) => {
                self.show_error("Export Failed", &format!("Could not load schema: {}", e));
                return;
            }
        };

        let tmp_dir = std::env::temp_dir();
        let backup_path = tmp_dir.join("expenses-export-BACKUP");

        // Remove old temp file if exists
        std::fs::remove_file(&backup_path).ok();

        match self.create_myexpenses_backup(&backup_path, &schema_sql) {
            Ok(()) => {
                match self.zip_backup(&backup_path, zip_path) {
                    Ok(()) => {
                        self.show_info("Export Complete", "MyExpenses backup created successfully.");
                    }
                    Err(e) => {
                        self.show_error("Export Failed", &format!("Could not create ZIP: {}", e));
                    }
                }
            }
            Err(e) => {
                self.show_error("Export Failed", &format!("Could not create backup: {}", e));
            }
        }

        std::fs::remove_file(&backup_path).ok();
    }

    fn create_myexpenses_backup(&self, backup_path: &Path, schema_sql: &str) -> Result<(), String> {
        let conn = Connection::open(backup_path).map_err(|e| e.to_string())?;
        conn.execute_batch(schema_sql).map_err(|e| e.to_string())?;

        let accounts = self.db().get_accounts().map_err(|e| e.to_string())?;
        let mut account_id_map = std::collections::HashMap::new();

        for (i, account) in accounts.iter().enumerate() {
            let me_id = (i + 1) as i64;
            account_id_map.insert(account.id, me_id);

            // Get opening balance for this account
            let opening: Option<f64> = self.db().connection().query_row(
                "SELECT amount FROM expenses WHERE account_id = ?1 AND is_opening_balance = 1",
                params![account.id],
                |row| row.get(0),
            ).ok();
            let opening_cents = opening.map(|a| (a * 100.0).round() as i64).unwrap_or(0);

            let uuid = uuid::Uuid::new_v4().to_string();
            conn.execute(
                "INSERT INTO accounts (label, opening_balance, description, currency, type, color, uuid) \
                 VALUES (?1, ?2, '', 'EUR', 1, -3355444, ?3)",
                params![account.name, opening_cents, uuid],
            ).map_err(|e| e.to_string())?;
        }

        // Export payees
        let all_expenses = self.db().get_all_expenses_for_export().map_err(|e| e.to_string())?;
        let mut payee_id_map = std::collections::HashMap::new();

        for expense in &all_expenses {
            if !expense.payee.is_empty() && !payee_id_map.contains_key(&expense.payee) {
                conn.execute(
                    "INSERT INTO payee (name, name_normalized) VALUES (?1, ?2)",
                    params![expense.payee, expense.payee.to_lowercase()],
                ).map_err(|e| e.to_string())?;
                let pid = conn.last_insert_rowid();
                payee_id_map.insert(expense.payee.clone(), pid);
            }
        }

        // Export transactions (skip opening balances)
        for expense in &all_expenses {
            if expense.is_opening_balance { continue; }

            let me_account_id = match account_id_map.get(&expense.account_id) {
                Some(id) => *id,
                None => continue,
            };

            let amount_cents = if expense.is_income {
                (expense.amount * 100.0).round() as i64
            } else {
                -(expense.amount * 100.0).round() as i64
            };

            let timestamp = Self::date_str_to_timestamp(&expense.date);
            let payee_id = payee_id_map.get(&expense.payee).copied();
            let uuid = uuid::Uuid::new_v4().to_string();

            conn.execute(
                "INSERT INTO transactions \
                 (comment, date, value_date, amount, account_id, payee_id, cr_status, number, uuid) \
                 VALUES (?1, ?2, ?2, ?3, ?4, ?5, 'UNRECONCILED', '', ?6)",
                params![expense.note, timestamp, amount_cents, me_account_id, payee_id, uuid],
            ).map_err(|e| e.to_string())?;
        }

        Ok(())
    }

    fn zip_backup(
        &self,
        backup_path: &Path,
        zip_path: &Path,
    ) -> Result<(), String> {
        let file = std::fs::File::create(zip_path).map_err(|e| e.to_string())?;
        let mut zip = zip::ZipWriter::new(file);

        let options = zip::write::SimpleFileOptions::default()
            .compression_method(zip::CompressionMethod::Deflated);

        zip.start_file("BACKUP", options).map_err(|e| e.to_string())?;
        let backup_data = std::fs::read(backup_path).map_err(|e| e.to_string())?;
        zip.write_all(&backup_data).map_err(|e| e.to_string())?;
        zip.finish().map_err(|e| e.to_string())?;
        Ok(())
    }

    fn date_str_to_timestamp(date_str: &str) -> i64 {
        // Try "YYYY-MM-DD HH:MM" first, then "YYYY-MM-DD"
        if let Ok(dt) = chrono::NaiveDateTime::parse_from_str(date_str, "%Y-%m-%d %H:%M") {
            dt.and_local_timezone(chrono::Local).unwrap().timestamp()
        } else if let Ok(d) = chrono::NaiveDate::parse_from_str(date_str, "%Y-%m-%d") {
            d.and_hms_opt(0, 0, 0).unwrap()
                .and_local_timezone(chrono::Local).unwrap().timestamp()
        } else {
            chrono::Local::now().timestamp()
        }
    }

    // --- Database Export ---

    pub(crate) fn on_export_db(&self) {
        let timestamp = chrono::Local::now().format("%Y-%m-%d_%H-%M-%S");
        let dialog = gtk::FileDialog::builder()
            .title("Export Database")
            .initial_name(format!("expenses-backup-{}.db", timestamp))
            .build();

        dialog.save(Some(self), None::<&gio::Cancellable>, glib::clone!(
            #[weak(rename_to = window)]
            self,
            move |result| {
                if let Ok(file) = result {
                    if let Some(path) = file.path() {
                        window.do_export_db(&path);
                    }
                }
            }
        ));
    }

    fn do_export_db(&self, dest_path: &Path) {
        match self.db().connection().backup(
            rusqlite::DatabaseName::Main,
            dest_path,
            None,
        ) {
            Ok(()) => {
                // Convert WAL to DELETE journal mode for portability
                if let Ok(dst) = Connection::open(dest_path) {
                    dst.execute_batch("PRAGMA journal_mode=DELETE;").ok();
                }
                self.show_info("Export Complete", "Database exported successfully.");
            }
            Err(e) => {
                self.show_error("Export Failed", &format!("{}", e));
            }
        }
    }

    // --- Database Import ---

    pub(crate) fn on_import_db(&self) {
        let dialog = gtk::FileDialog::builder()
            .title("Import Database")
            .build();

        let filter = gtk::FileFilter::new();
        filter.add_pattern("*.db");
        filter.set_name(Some("SQLite Database"));
        let filters = gio::ListStore::new::<gtk::FileFilter>();
        filters.append(&filter);
        dialog.set_filters(Some(&filters));

        dialog.open(Some(self), None::<&gio::Cancellable>, glib::clone!(
            #[weak(rename_to = window)]
            self,
            move |result| {
                if let Ok(file) = result {
                    if let Some(path) = file.path() {
                        window.confirm_import_db(&path);
                    }
                }
            }
        ));
    }

    fn confirm_import_db(&self, path: &Path) {
        let dialog = adw::AlertDialog::builder()
            .heading("Import Database?")
            .body("This will replace ALL current data with the imported database. This cannot be undone.")
            .build();
        dialog.add_response("cancel", "Cancel");
        dialog.add_response("import", "Import");
        dialog.set_response_appearance("import", adw::ResponseAppearance::Destructive);

        let path = path.to_path_buf();
        dialog.choose(self, None::<&gio::Cancellable>, glib::clone!(
            #[weak(rename_to = window)]
            self,
            move |response| {
                if response == "import" {
                    window.do_import_db(&path);
                }
            }
        ));
    }

    fn do_import_db(&self, path: &Path) {
        match Connection::open_with_flags(path, rusqlite::OpenFlags::SQLITE_OPEN_READ_ONLY) {
            Ok(src) => {
                // Backup source database to the app's database path
                let db_path = Database::db_path();
                match src.backup(rusqlite::DatabaseName::Main, &db_path, None) {
                    Ok(()) => {
                        // Re-initialize database connection
                        self.init_db();
                        self.setup_accounts();
                        self.refresh_expenses();
                        self.show_info("Import Complete", "Database imported successfully.");
                    }
                    Err(e) => {
                        self.show_error("Import Failed", &format!("{}", e));
                    }
                }
            }
            Err(e) => {
                self.show_error("Import Failed", &format!("Could not open file: {}", e));
            }
        }
    }

    // --- Helper dialogs ---

    fn show_info(&self, heading: &str, body: &str) {
        let dialog = adw::AlertDialog::builder()
            .heading(heading)
            .body(body)
            .build();
        dialog.add_response("ok", "OK");
        dialog.present(Some(self));
    }

    fn show_error(&self, heading: &str, body: &str) {
        let dialog = adw::AlertDialog::builder()
            .heading(heading)
            .body(body)
            .build();
        dialog.add_response("ok", "OK");
        dialog.present(Some(self));
    }
}

