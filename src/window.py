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

from gi.repository import Adw, Gtk, GLib, Gio
import json
import os
from datetime import datetime

@Gtk.Template(resource_path='/io/github/nico359/expenses/window.ui')
class ExpensesWindow(Adw.ApplicationWindow):
    __gtype_name__ = 'ExpensesWindow'

    amount_entry = Gtk.Template.Child()
    payee_entry = Gtk.Template.Child()
    add_button = Gtk.Template.Child()
    expense_list = Gtk.Template.Child()
    total_label = Gtk.Template.Child()
    account_dropdown = Gtk.Template.Child()
    manage_accounts_button = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Data storage
        self.data = {
            'accounts': ['Default'],
            'current_account': 'Default',
            'expenses': {}  # {account_name: [expenses]}
        }
        self.data_file = os.path.join(GLib.get_user_data_dir(), 'expenses.json')

        # Load existing data
        self.load_data()

        # Setup autocomplete
        self.setup_payee_autocomplete()

        # Setup account dropdown
        self.setup_account_dropdown()

        # Connect signals
        self.add_button.connect('clicked', self.on_add_expense)
        self.amount_entry.connect('entry-activated', self.on_add_expense)
        self.payee_entry.connect('entry-activated', self.on_add_expense)
        self.account_dropdown.connect('notify::selected', self.on_account_changed)
        self.manage_accounts_button.connect('clicked', self.on_manage_accounts)

        # Update UI
        self.update_expense_list()
        self.update_total()

    def setup_payee_autocomplete(self):
        """Setup autocomplete for payee entry"""
        # Create completion
        completion = Gtk.EntryCompletion()

        # Create list store for payees
        self.payee_store = Gtk.ListStore(str)
        completion.set_model(self.payee_store)
        completion.set_text_column(0)
        completion.set_minimum_key_length(1)
        completion.set_inline_completion(True)
        completion.set_popup_completion(True)

        # Get the internal GtkText widget from AdwEntryRow
        # This is a bit of a workaround for Adwaita entry rows
        self.payee_text_widget = None
        for child in self.payee_entry:
            if isinstance(child, Gtk.Text):
                self.payee_text_widget = child
                self.payee_text_widget.set_completion(completion)
                break

        self.update_payee_suggestions()

    def update_payee_suggestions(self):
        """Update autocomplete suggestions based on existing payees"""
        payees = set()

        # Collect all unique payees from all accounts
        for account_expenses in self.data['expenses'].values():
            for expense in account_expenses:
                payees.add(expense['payee'])

        # Update the store
        self.payee_store.clear()
        for payee in sorted(payees):
            self.payee_store.append([payee])

    def setup_account_dropdown(self):
        """Setup the account dropdown"""
        # Create string list
        self.account_list = Gtk.StringList()
        for account in self.data['accounts']:
            self.account_list.append(account)

        self.account_dropdown.set_model(self.account_list)

        # Set current account
        try:
            index = self.data['accounts'].index(self.data['current_account'])
            self.account_dropdown.set_selected(index)
        except ValueError:
            self.account_dropdown.set_selected(0)

    def on_account_changed(self, dropdown, param):
        """Handle account selection change"""
        selected = dropdown.get_selected()
        if selected != Gtk.INVALID_LIST_POSITION:
            self.data['current_account'] = self.data['accounts'][selected]
            self.save_data()
            self.update_expense_list()
            self.update_total()

    def on_manage_accounts(self, button):
        """Show account management dialog"""
        dialog = Adw.MessageDialog.new(self)
        dialog.set_heading("Manage Accounts")
        dialog.set_body("Enter a new account name:")

        # Create entry for new account
        entry = Gtk.Entry()
        entry.set_placeholder_text("e.g., Cash, Credit Card, Savings")
        entry.set_margin_start(12)
        entry.set_margin_end(12)
        entry.set_margin_top(12)
        entry.set_margin_bottom(12)

        dialog.set_extra_child(entry)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("add", "Add Account")
        dialog.set_response_appearance("add", Adw.ResponseAppearance.SUGGESTED)

        dialog.connect('response', self.on_add_account_response, entry)
        dialog.present()

    def on_add_account_response(self, dialog, response, entry):
        """Handle add account dialog response"""
        if response == "add":
            account_name = entry.get_text().strip()
            if account_name and account_name not in self.data['accounts']:
                self.data['accounts'].append(account_name)
                self.data['expenses'][account_name] = []
                self.account_list.append(account_name)
                self.save_data()

                # Select the new account
                index = self.data['accounts'].index(account_name)
                self.account_dropdown.set_selected(index)

    def load_data(self):
        """Load data from JSON file"""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    loaded_data = json.load(f)
                    # Merge with defaults
                    if 'accounts' in loaded_data:
                        self.data['accounts'] = loaded_data['accounts']
                    if 'current_account' in loaded_data:
                        self.data['current_account'] = loaded_data['current_account']
                    if 'expenses' in loaded_data:
                        self.data['expenses'] = loaded_data['expenses']
                    else:
                        # Convert old format if exists
                        if isinstance(loaded_data, list):
                            self.data['expenses']['Default'] = loaded_data
            except:
                pass

        # Ensure current account exists in accounts list
        if self.data['current_account'] not in self.data['accounts']:
            self.data['current_account'] = self.data['accounts'][0]

        # Ensure all accounts have expense lists
        for account in self.data['accounts']:
            if account not in self.data['expenses']:
                self.data['expenses'][account] = []

    def save_data(self):
        """Save data to JSON file"""
        try:
            os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
            with open(self.data_file, 'w') as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            print(f"Error saving data: {e}")

    def get_current_expenses(self):
        """Get expenses for current account"""
        account = self.data['current_account']
        if account not in self.data['expenses']:
            self.data['expenses'][account] = []
        return self.data['expenses'][account]

    def on_add_expense(self, widget):
        """Handle adding a new expense"""
        amount_text = self.amount_entry.get_text().strip()
        payee_text = self.payee_entry.get_text().strip()

        if not amount_text or not payee_text:
            return

        try:
            # Parse amount (accept both comma and dot as decimal separator)
            amount = float(amount_text.replace(',', '.'))

            # Create expense entry
            expense = {
                'amount': amount,
                'payee': payee_text,
                'date': datetime.now().strftime('%Y-%m-%d %H:%M')
            }

            # Add to current account
            expenses = self.get_current_expenses()
            expenses.append(expense)

            # Save to file
            self.save_data()

            # Update autocomplete suggestions
            self.update_payee_suggestions()

            # Update UI
            self.update_expense_list()
            self.update_total()

            # Clear inputs
            self.amount_entry.set_text('')
            self.payee_entry.set_text('')
            self.amount_entry.grab_focus()

        except ValueError:
            # Invalid number format
            dialog = Adw.MessageDialog.new(self)
            dialog.set_heading("Invalid Amount")
            dialog.set_body("Please enter a valid number for the amount.")
            dialog.add_response("ok", "OK")
            dialog.present()

    def update_expense_list(self):
        """Update the expense list display"""
        # Clear existing items
        while True:
            row = self.expense_list.get_row_at_index(0)
            if row is None:
                break
            self.expense_list.remove(row)

        # Get expenses for current account
        expenses = self.get_current_expenses()

        # Add expenses in reverse order (newest first)
        for i, expense in enumerate(reversed(expenses)):
            row = self.create_expense_row(expense, len(expenses) - 1 - i)
            self.expense_list.append(row)

    def create_expense_row(self, expense, index):
        """Create a list row for an expense"""
        row = Adw.ActionRow()
        row.set_title(expense['payee'])
        row.set_subtitle(expense['date'])

        # Amount label
        amount_label = Gtk.Label()
        amount_label.set_text(f"{expense['amount']:.2f} €")
        amount_label.add_css_class('title-3')
        amount_label.add_css_class('accent')

        # Delete button
        delete_button = Gtk.Button()
        delete_button.set_icon_name('user-trash-symbolic')
        delete_button.set_valign(Gtk.Align.CENTER)
        delete_button.add_css_class('flat')
        delete_button.connect('clicked', self.on_delete_expense, index)

        # Add to row
        row.add_suffix(amount_label)
        row.add_suffix(delete_button)

        return row

    def on_delete_expense(self, button, index):
        """Handle deleting an expense"""
        expenses = self.get_current_expenses()
        if 0 <= index < len(expenses):
            expenses.pop(index)
            self.save_data()
            self.update_expense_list()
            self.update_total()
            self.update_payee_suggestions()

    def update_total(self):
        """Update the total amount display"""
        expenses = self.get_current_expenses()
        total = sum(expense['amount'] for expense in expenses)
        self.total_label.set_text(f"{total:.2f} €")
