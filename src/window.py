# window.py
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

from gi.repository import Adw, Gtk, GLib, Gio

from .accounts import AccountsMixin
from .db import Database
from .expenses import ExpensesMixin
from .importexport import ImportExportMixin


@Gtk.Template(resource_path='/io/github/nico359/expenses/window.ui')
class ExpensesWindow(AccountsMixin, ExpensesMixin, ImportExportMixin,
                     Adw.ApplicationWindow):
    __gtype_name__ = 'ExpensesWindow'

    amount_entry = Gtk.Template.Child()
    payee_entry = Gtk.Template.Child()
    note_entry = Gtk.Template.Child()
    income_switch = Gtk.Template.Child()
    add_button = Gtk.Template.Child()
    expense_list = Gtk.Template.Child()
    total_label = Gtk.Template.Child()
    account_dropdown = Gtk.Template.Child()
    account_options_button = Gtk.Template.Child()
    search_entry = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Initialize SQLite database
        db_path = os.path.join(GLib.get_user_data_dir(), 'expenses.db')
        self.db = Database(db_path)

        # Ensure at least one account exists
        if not self.db.get_accounts():
            self.db.add_account('Default')
            self.db.set_setting('current_account', 'Default')

        self.current_account = self.db.get_setting(
            'current_account',
            self.db.get_accounts()[0]
        )
        self.search_query = ''
        self.page_size = 50
        self.displayed_count = 0

        # Process recurring expenses on startup
        self.process_recurring_expenses()

        # Setup autocomplete
        self.setup_payee_autocomplete()

        # Setup account dropdown
        self.setup_account_dropdown()

        # Connect signals
        self.add_button.connect('clicked', self.on_add_expense)
        self.amount_entry.connect('entry-activated', self.on_add_expense)
        self.payee_entry.connect('entry-activated', self.on_add_expense)
        self.account_dropdown.connect('notify::selected', self.on_account_changed)
        self.account_options_button.connect('clicked', self.on_account_options)
        self.search_entry.connect('search-changed', self.on_search_changed)

        # Setup import/export actions
        import_action = Gio.SimpleAction.new("import-db", None)
        import_action.connect("activate", self.on_import_database)
        self.add_action(import_action)

        export_action = Gio.SimpleAction.new("export-db", None)
        export_action.connect("activate", self.on_export_database)
        self.add_action(export_action)

        import_backup_action = Gio.SimpleAction.new("import-backup", None)
        import_backup_action.connect("activate", self.on_import_backup)
        self.add_action(import_backup_action)

        export_me_action = Gio.SimpleAction.new("export-myexpenses", None)
        export_me_action.connect("activate", self.on_export_myexpenses)
        self.add_action(export_me_action)

        # Close database when window is destroyed
        self.connect('close-request', self._on_close_request)

        # Update UI
        self.update_expense_list()
        self.update_total()

    def _on_close_request(self, window):
        self.db.close()
        return False

    def setup_payee_autocomplete(self):
        """Setup autocomplete for payee entry"""
        suggestion_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        scrollable = Gtk.ScrolledWindow()
        scrollable.set_max_content_height(250)
        scrollable.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.payee_list = Gtk.ListBox()
        self.payee_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.payee_list.connect('row-activated', self.on_payee_selected)

        scrollable.set_child(self.payee_list)
        suggestion_box.append(scrollable)

        # Create a popover with suggestions — autohide off so it
        # never steals keyboard focus from the entry.
        self.payee_popover = Gtk.Popover()
        self.payee_popover.set_child(suggestion_box)
        self.payee_popover.set_position(Gtk.PositionType.BOTTOM)
        self.payee_popover.set_has_arrow(False)
        self.payee_popover.set_autohide(False)
        self.payee_popover.set_parent(self.payee_entry)

        # Store all unique payees for filtering
        self.all_payees = []

        # Connect to payee entry changes and focus
        self.payee_entry.connect('notify::text', self.on_payee_changed)

        # Hide suggestions when the entry loses focus
        focus_controller = Gtk.EventControllerFocus()
        focus_controller.connect('leave', lambda _ctrl: self.payee_popover.popdown())
        self.payee_entry.add_controller(focus_controller)

        self.update_payee_suggestions()

    def update_payee_suggestions(self):
        """Update autocomplete suggestions based on existing payees"""
        self.all_payees = self.db.get_all_payees()

    def on_payee_changed(self, entry, param):
        """Handle payee entry text changes to show suggestions"""
        text = entry.get_text().strip()

        if len(text) < 1:
            self.payee_popover.popdown()
            return

        # Filter suggestions based on text
        text_lower = text.lower()
        matching_payees = [p for p in self.all_payees if text_lower in p.lower()]

        # Clear and rebuild list
        while self.payee_list.get_first_child():
            self.payee_list.remove(self.payee_list.get_first_child())

        for payee in matching_payees:
            label = Gtk.Label(label=payee, xalign=0)
            label.set_margin_start(12)
            label.set_margin_end(12)
            label.set_margin_top(8)
            label.set_margin_bottom(8)
            row = Gtk.ListBoxRow(child=label)
            self.payee_list.append(row)

        if matching_payees:
            self.payee_popover.popup()
        else:
            self.payee_popover.popdown()

    def on_payee_selected(self, list_box, row):
        """Handle payee selection from dropdown"""
        label = row.get_child()
        if label:
            payee_text = label.get_label()
            self.payee_entry.set_text(payee_text)
            self.payee_popover.popdown()

    def update_total(self):
        """Update the total amount display"""
        total = self.db.get_account_total(self.current_account)
        self.total_label.set_text(f"{total:.2f} €")

    def on_search_changed(self, search_entry):
        """Handle search query changes"""
        self.search_query = search_entry.get_text()
        self.update_expense_list()
