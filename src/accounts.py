# accounts.py
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

from gi.repository import Adw, Gtk


class AccountsMixin:
    """Account management: dropdown, add and delete dialogs."""

    def setup_account_dropdown(self):
        """Setup the account dropdown"""
        accounts = self.db.get_accounts()

        # Create string list including existing accounts + add new option
        self.account_list = Gtk.StringList()
        for account in accounts:
            self.account_list.append(account)
        # Add a special entry for adding new account
        self.account_list.append("+ New Account")

        self.account_dropdown.set_model(self.account_list)

        # Create custom factory for dropdown items
        factory = Gtk.SignalListItemFactory()
        factory.connect('setup', self._setup_account_item)
        factory.connect('bind', self._bind_account_item)
        self.account_dropdown.set_factory(factory)

        # Set current account
        try:
            index = accounts.index(self.current_account)
            self.account_dropdown.set_selected(index)
        except ValueError:
            self.account_dropdown.set_selected(0)

        # Connect selection change
        self.account_dropdown.connect('notify::selected', self.on_account_changed)

    def _setup_account_item(self, factory, item):
        """Setup account dropdown item"""
        item.set_child(Gtk.Label())

    def _bind_account_item(self, factory, item):
        """Bind account dropdown item"""
        label = item.get_child()
        obj = item.get_item()
        if obj:
            label.set_text(obj.get_string())

    def on_account_changed(self, dropdown, param):
        """Handle account selection change"""
        selected = dropdown.get_selected()
        accounts = self.db.get_accounts()
        if selected != Gtk.INVALID_LIST_POSITION:
            # Check if "Add Account" was selected
            if selected == len(accounts):
                # Reset to previous selection and show add account dialog
                try:
                    prev_index = accounts.index(self.current_account)
                    self.account_dropdown.set_selected(prev_index)
                except ValueError:
                    self.account_dropdown.set_selected(0)
                self.on_add_account()
            else:
                # Normal account selection
                self.current_account = accounts[selected]
                self.db.set_setting('current_account', self.current_account)
                self.update_expense_list()
                self.update_total()

    def on_add_account(self):
        """Show add account dialog"""
        dialog = Adw.MessageDialog.new(self)
        dialog.set_heading("New Account")
        dialog.set_body("Enter account name:")

        # Create entry for new account
        entry = Gtk.Entry()
        entry.set_placeholder_text("e.g., Cash, Credit Card, Savings")
        entry.set_margin_start(12)
        entry.set_margin_end(12)
        entry.set_margin_top(12)
        entry.set_margin_bottom(12)

        dialog.set_extra_child(entry)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("add", "Create")
        dialog.set_response_appearance("add", Adw.ResponseAppearance.SUGGESTED)

        dialog.connect('response', self.on_add_account_response, entry)
        dialog.present()

    def on_add_account_response(self, dialog, response, entry):
        """Handle add account dialog response"""
        if response == "add":
            account_name = entry.get_text().strip()
            if account_name and account_name not in self.db.get_accounts():
                self.db.add_account(account_name)

                # Rebuild the dropdown with new account
                self.setup_account_dropdown()

                # Select the new account
                index = self.db.get_accounts().index(account_name)
                self.account_dropdown.set_selected(index)

    def on_account_options(self, button):
        """Show account options menu"""
        if len(self.db.get_accounts()) <= 1:
            # Show message that at least one account must exist
            dialog = Adw.MessageDialog.new(self)
            dialog.set_heading("Cannot Delete Account")
            dialog.set_body("You must have at least one account.")
            dialog.add_response("ok", "OK")
            dialog.present()
            return

        # Show delete confirmation dialog
        dialog = Adw.MessageDialog.new(self)
        dialog.set_heading("Delete Account?")
        dialog.set_body(f"Are you sure you want to delete the account '{self.current_account}'? All expenses in this account will be permanently deleted.")
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("delete", "Delete")
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")

        dialog.connect('response', self.on_delete_account_response)
        dialog.present()

    def on_delete_account_response(self, dialog, response):
        """Handle delete account confirmation"""
        if response == "delete":
            self.db.delete_account(self.current_account)

            # Switch to first available account
            accounts = self.db.get_accounts()
            if accounts:
                self.current_account = accounts[0]
                self.db.set_setting('current_account', self.current_account)

            # Rebuild UI
            self.setup_account_dropdown()
            self.update_expense_list()
            self.update_total()
