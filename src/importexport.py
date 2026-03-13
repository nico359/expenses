# importexport.py
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

import os
import sqlite3
import tempfile
import uuid
import zipfile
from datetime import datetime

from gi.repository import Adw, Gtk, GLib, Gio


class ImportExportMixin:
    """Import and export: MyExpenses backup, raw DB backup/restore."""

    def on_import_database(self, action, param):
        """Show file chooser for importing MyExpenses backup (zip or raw DB)"""
        dialog = Gtk.FileDialog()
        dialog.set_title("Import from MyExpenses")
        dialog.set_modal(True)

        # Set initial folder to home directory
        home_dir = GLib.get_home_dir()
        try:
            initial_folder = Gio.File.new_for_path(home_dir)
            dialog.set_initial_folder(initial_folder)
        except Exception:
            pass

        filters = Gio.ListStore.new(Gtk.FileFilter)

        backup_filter = Gtk.FileFilter()
        backup_filter.set_name("MyExpenses Backups")
        backup_filter.add_pattern("*.zip")
        backup_filter.add_pattern("BACKUP")
        backup_filter.add_pattern("*.db")
        backup_filter.add_pattern("*.sqlite")
        filters.append(backup_filter)

        all_filter = Gtk.FileFilter()
        all_filter.set_name("All Files")
        all_filter.add_pattern("*")
        filters.append(all_filter)

        dialog.set_filters(filters)
        dialog.open(self, None, self.on_import_file_selected)

    def on_import_file_selected(self, dialog, result):
        """Handle file selection for import"""
        try:
            file = dialog.open_finish(result)
            path = file.get_path()

            # If it's a zip, extract the BACKUP database to a temp file
            if zipfile.is_zipfile(path):
                path = self._extract_backup_from_zip(path)

            accounts_imported, transactions_imported = self.import_sqlite_database(path)

            success_dialog = Adw.MessageDialog.new(self)
            success_dialog.set_heading("Import Successful")
            success_dialog.set_body(f"Imported {accounts_imported} account(s) and {transactions_imported} transaction(s)")
            success_dialog.add_response("ok", "OK")
            success_dialog.set_response_appearance("ok", Adw.ResponseAppearance.DEFAULT)
            success_dialog.connect('response', lambda d, r: self.on_import_complete())
            success_dialog.present()

        except GLib.Error as e:
            error_dialog = Adw.MessageDialog.new(self)
            error_dialog.set_heading("Import Failed")
            error_dialog.set_body(f"Could not open file: {str(e)}")
            error_dialog.add_response("ok", "OK")
            error_dialog.present()
        except Exception as e:
            error_dialog = Adw.MessageDialog.new(self)
            error_dialog.set_heading("Import Failed")
            error_dialog.set_body(str(e))
            error_dialog.add_response("ok", "OK")
            error_dialog.present()

    def _extract_backup_from_zip(self, zip_path):
        """Extract the BACKUP database from a MyExpenses zip archive.

        Returns the path to the extracted file.
        """
        with zipfile.ZipFile(zip_path, 'r') as zf:
            names = zf.namelist()
            # Look for the BACKUP file (the actual SQLite database)
            backup_name = None
            for name in names:
                if name == 'BACKUP' or name.endswith('/BACKUP'):
                    backup_name = name
                    break

            if backup_name is None:
                raise ValueError(
                    "No BACKUP database found in the zip file.\n"
                    f"Contents: {', '.join(names)}"
                )

            tmp_dir = tempfile.mkdtemp(prefix='expenses-import-')
            zf.extract(backup_name, tmp_dir)
            extracted = os.path.join(tmp_dir, backup_name)

            # Guard against path traversal in malicious zip entries
            if not os.path.abspath(extracted).startswith(
                os.path.abspath(tmp_dir) + os.sep
            ):
                raise ValueError("Zip contains unsafe path")

            return extracted

    def import_sqlite_database(self, db_path):
        """Import data from SQLite database"""
        conn = None
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Fetch all accounts with opening balance
            cursor.execute("""
                SELECT _id, label, opening_balance FROM accounts
                ORDER BY sort_key ASC
            """)
            accounts = {}
            account_list = []
            opening_balances = {}

            for account_id, account_label, opening_balance_cents in cursor.fetchall():
                account_name = account_label.strip()
                account_list.append(account_name)
                accounts[account_id] = account_name
                opening_balances[account_id] = opening_balance_cents if opening_balance_cents else 0

            # Start with imported accounts or default if none
            if not account_list:
                account_list = ['Default']

            # Fetch all transactions with payee information
            cursor.execute("""
                SELECT t.account_id, t.amount, t.date, t.comment, p.name
                FROM transactions t
                LEFT JOIN payee p ON t.payee_id = p._id
                WHERE t.parent_id IS NULL
                ORDER BY t.date ASC
            """)

            expenses_data = {account: [] for account in account_list}

            # Add opening balance as initial transaction for each account
            for account_id, account_name in accounts.items():
                opening_balance_cents = opening_balances[account_id]
                if opening_balance_cents > 0:
                    opening_balance_euros = opening_balance_cents / 100.0
                    opening_expense = {
                        'amount': opening_balance_euros,
                        'payee': 'Opening Balance',
                        'note': 'Initial balance imported from database',
                        'date': '0000-01-01 00:00',
                        'is_opening_balance': True,
                        'is_income': True
                    }
                    expenses_data[account_name].insert(0, opening_expense)

            for account_id, amount_cents, timestamp, comment, payee_name in cursor.fetchall():
                # Get account name
                account_name = accounts.get(account_id, 'Default')

                # Convert amount from cents to euros
                amount_euros = amount_cents / 100.0
                is_income = amount_euros > 0

                # Convert timestamp (unix epoch in seconds) to ISO format
                try:
                    date_obj = datetime.fromtimestamp(timestamp)
                    date_str = date_obj.strftime('%Y-%m-%d %H:%M')
                except (ValueError, OSError, OverflowError):
                    date_str = datetime.now().strftime('%Y-%m-%d %H:%M')

                # Use payee name if available, otherwise fall back to default
                if payee_name:
                    payee = payee_name.strip()
                else:
                    payee = 'Unknown'

                expense = {
                    'amount': amount_euros,
                    'payee': payee,
                    'note': comment.strip() if comment else '',
                    'date': date_str,
                    'is_income': is_income
                }

                if account_name not in expenses_data:
                    expenses_data[account_name] = []

                expenses_data[account_name].append(expense)

            conn.close()

            # Replace all data via the database
            imported_data = {
                'accounts': account_list,
                'current_account': account_list[0] if account_list else 'Default',
                'expenses': expenses_data
            }
            self.db.replace_all_data(imported_data)
            self.current_account = imported_data['current_account']

            # Return counts for the success message
            total_transactions = sum(len(expenses) for expenses in expenses_data.values())
            return len(account_list), total_transactions

        except Exception as e:
            print(f"Error importing database: {e}")
            raise
        finally:
            if conn:
                conn.close()

    def on_import_complete(self):
        """Handle import completion - refresh UI"""
        self.setup_account_dropdown()
        self.update_expense_list()
        self.update_total()
        self.update_payee_suggestions()

    # ── MyExpenses-compatible export ───────────────────────────────────

    def on_export_myexpenses(self, action, param):
        """Export data as a MyExpenses-compatible backup zip"""
        dialog = Gtk.FileDialog()
        dialog.set_title("Export for MyExpenses")
        dialog.set_modal(True)

        now = datetime.now()
        dialog.set_initial_name(
            f"myexpenses-backup-{now.strftime('%Y%m%d-%H%M%S')}.zip"
        )

        filters = Gio.ListStore.new(Gtk.FileFilter)
        zip_filter = Gtk.FileFilter()
        zip_filter.set_name("Zip Archives")
        zip_filter.add_pattern("*.zip")
        filters.append(zip_filter)
        dialog.set_filters(filters)

        dialog.save(self, None, self._on_export_myexpenses_selected)

    def _on_export_myexpenses_selected(self, dialog, result):
        try:
            file = dialog.save_finish(result)
            dest_path = file.get_path()
        except GLib.Error:
            return  # user cancelled

        try:
            self._build_myexpenses_backup(dest_path)

            success = Adw.MessageDialog.new(self)
            success.set_heading("Export Successful")
            success.set_body(
                f"MyExpenses-compatible backup exported to:\n{dest_path}"
            )
            success.add_response("ok", "OK")
            success.present()

        except Exception as e:
            error = Adw.MessageDialog.new(self)
            error.set_heading("Export Failed")
            error.set_body(str(e))
            error.add_response("ok", "OK")
            error.present()

    def _build_myexpenses_backup(self, zip_path):
        """Build a MyExpenses-compatible BACKUP database and package as zip"""
        # Load schema from bundled gresource
        schema_bytes = Gio.resources_lookup_data(
            '/io/github/nico359/expenses/myexpenses_schema.sql',
            Gio.ResourceLookupFlags.NONE,
        )
        schema_sql = schema_bytes.get_data().decode('utf-8')

        with tempfile.TemporaryDirectory(prefix='expenses-export-') as tmp_dir:
            db_path = os.path.join(tmp_dir, 'BACKUP')
            conn = sqlite3.connect(db_path)
            conn.executescript(schema_sql)

            accounts = self.db.get_accounts()
            account_id_map = {}  # our account name → MyExpenses _id

            for name in accounts:
                our_id = self.db._get_account_id(name)

                # Get opening balance (stored as a pseudo-expense)
                row = self.db.conn.execute(
                    "SELECT amount, is_income FROM expenses "
                    "WHERE account_id = ? AND is_opening_balance = 1",
                    (our_id,),
                ).fetchone()
                opening_cents = round(row[0] * 100) if row else 0

                conn.execute(
                    "INSERT INTO accounts "
                    "(label, opening_balance, description, currency, type, "
                    " color, uuid) "
                    "VALUES (?, ?, '', 'EUR', 1, -3355444, ?)",
                    (name, opening_cents, str(uuid.uuid4())),
                )
                me_id = conn.execute(
                    "SELECT last_insert_rowid()"
                ).fetchone()[0]
                account_id_map[name] = me_id

            # Build payee lookup
            all_payees = self.db.get_all_payees()
            payee_id_map = {}
            for payee_name in all_payees:
                conn.execute(
                    "INSERT INTO payee (name, name_normalized) VALUES (?, ?)",
                    (payee_name, payee_name.lower()),
                )
                pid = conn.execute(
                    "SELECT last_insert_rowid()"
                ).fetchone()[0]
                payee_id_map[payee_name] = pid

            # Export transactions
            for name in accounts:
                our_id = self.db._get_account_id(name)
                me_account_id = account_id_map[name]

                rows = self.db.conn.execute(
                    "SELECT amount, payee, note, date, is_income "
                    "FROM expenses "
                    "WHERE account_id = ? AND is_opening_balance = 0 "
                    "ORDER BY id",
                    (our_id,),
                ).fetchall()

                for amount, payee, note, date_str, is_income in rows:
                    amount_cents = round(amount * 100)
                    if not is_income:
                        amount_cents = -amount_cents

                    try:
                        dt = datetime.strptime(date_str, '%Y-%m-%d %H:%M')
                    except ValueError:
                        dt = datetime.strptime(date_str, '%Y-%m-%d')
                    timestamp = int(dt.timestamp())

                    payee_id = payee_id_map.get(payee)

                    conn.execute(
                        "INSERT INTO transactions "
                        "(comment, date, value_date, amount, account_id, "
                        " payee_id, cr_status, number, uuid) "
                        "VALUES (?, ?, ?, ?, ?, ?, 'UNRECONCILED', '', ?)",
                        (note or '', timestamp, timestamp, amount_cents,
                         me_account_id, payee_id, str(uuid.uuid4())),
                    )

            conn.commit()
            conn.close()

            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.write(db_path, 'BACKUP')

    # ── Database export / import ───────────────────────────────────────

    def on_export_database(self, action, param):
        """Export the database as a .db file"""
        dialog = Gtk.FileDialog()
        dialog.set_title("Export Database")
        dialog.set_modal(True)

        now = datetime.now()
        dialog.set_initial_name(
            f"expenses-backup-{now.strftime('%Y%m%d-%H%M%S')}.db"
        )

        filters = Gio.ListStore.new(Gtk.FileFilter)
        db_filter = Gtk.FileFilter()
        db_filter.set_name("SQLite Databases")
        db_filter.add_pattern("*.db")
        filters.append(db_filter)
        dialog.set_filters(filters)

        dialog.save(self, None, self._on_export_db_selected)

    def _on_export_db_selected(self, dialog, result):
        try:
            file = dialog.save_finish(result)
            dest_path = file.get_path()

            # Build the export in a temp file (writable), switch away from
            # WAL mode there, then copy the clean result to the portal path.
            tmp_fd, tmp_path = tempfile.mkstemp(suffix='.db')
            os.close(tmp_fd)
            try:
                dst = sqlite3.connect(tmp_path)
                self.db.conn.backup(dst)
                dst.execute("PRAGMA journal_mode=DELETE")
                dst.close()

                import shutil
                shutil.copy2(tmp_path, dest_path)
            finally:
                os.unlink(tmp_path)

            success = Adw.MessageDialog.new(self)
            success.set_heading("Export Successful")
            success.set_body(f"Database exported to:\n{dest_path}")
            success.add_response("ok", "OK")
            success.present()

        except GLib.Error:
            pass  # user cancelled
        except Exception as e:
            error = Adw.MessageDialog.new(self)
            error.set_heading("Export Failed")
            error.set_body(str(e))
            error.add_response("ok", "OK")
            error.present()

    def on_import_backup(self, action, param):
        """Import a previously exported .db file"""
        dialog = Gtk.FileDialog()
        dialog.set_title("Import Database")
        dialog.set_modal(True)

        filters = Gio.ListStore.new(Gtk.FileFilter)
        db_filter = Gtk.FileFilter()
        db_filter.set_name("SQLite Databases")
        db_filter.add_pattern("*.db")
        db_filter.add_pattern("*.sqlite")
        filters.append(db_filter)

        all_filter = Gtk.FileFilter()
        all_filter.set_name("All Files")
        all_filter.add_pattern("*")
        filters.append(all_filter)

        dialog.set_filters(filters)
        dialog.open(self, None, self._on_import_backup_selected)

    def _on_import_backup_selected(self, dialog, result):
        try:
            file = dialog.open_finish(result)
            path = file.get_path()
        except GLib.Error:
            return  # user cancelled

        # Ask for confirmation before replacing data
        confirm = Adw.MessageDialog.new(self)
        confirm.set_heading("Replace Existing Data?")
        confirm.set_body(
            "This will replace all current accounts, expenses and "
            "recurring definitions with the contents of the backup."
        )
        confirm.add_response("cancel", "Cancel")
        confirm.add_response("import", "Import")
        confirm.set_response_appearance(
            "import", Adw.ResponseAppearance.DESTRUCTIVE
        )
        confirm.set_default_response("cancel")
        confirm.connect("response", self._on_import_backup_confirmed, path)
        confirm.present()

    def _on_import_backup_confirmed(self, dialog, response, path):
        if response != "import":
            return

        try:
            # Open the backup file as immutable so SQLite won't try to
            # create -wal/-shm files next to it (the path may live on a
            # read-only Flatpak portal mount).
            from urllib.parse import quote
            uri = f"file:{quote(path, safe='/')}?immutable=1"
            src = sqlite3.connect(uri, uri=True)
            src.backup(self.db.conn)
            src.close()

            # Re-read settings
            accounts = self.db.get_accounts()
            self.current_account = self.db.get_setting(
                'current_account',
                accounts[0] if accounts else 'Default',
            )

            self.on_import_complete()

            success = Adw.MessageDialog.new(self)
            success.set_heading("Import Successful")
            success.set_body("Database restored from backup.")
            success.add_response("ok", "OK")
            success.present()

        except Exception as e:
            error = Adw.MessageDialog.new(self)
            error.set_heading("Import Failed")
            error.set_body(str(e))
            error.add_response("ok", "OK")
            error.present()
