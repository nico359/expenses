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
import os
import sqlite3
import tempfile
import uuid
import zipfile
from datetime import datetime

from .db import Database

@Gtk.Template(resource_path='/io/github/nico359/expenses/window.ui')
class ExpensesWindow(Adw.ApplicationWindow):
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

        # Update UI
        self.update_expense_list()
        self.update_total()

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

    def process_recurring_expenses(self):
        """Check and generate missing recurring expenses on startup"""
        from datetime import timedelta
        
        for recurring in self.db.get_recurring_expenses():
            account = recurring.get('account')
            if not account:
                continue
            
            # Get the start and last generated dates
            start_date = datetime.fromisoformat(recurring.get('start_date', datetime.now().isoformat()))
            last_generated = None
            if recurring.get('last_generated'):
                try:
                    last_generated = datetime.fromisoformat(recurring['last_generated'])
                except:
                    last_generated = start_date
            else:
                last_generated = start_date
            
            # Get frequency
            frequency = recurring.get('frequency', 'monthly')
            
            # Calculate next generation date
            current_date = datetime.now()
            next_date = last_generated
            
            # Generate missing entries
            while next_date <= current_date:
                # Check end date
                if recurring.get('end_date'):
                    try:
                        try:
                            end_date = datetime.fromisoformat(recurring['end_date'])
                        except:
                            end_date = datetime.fromisoformat(recurring['end_date'] + 'T23:59:59')
                        if next_date.date() > end_date.date():
                            break
                    except:
                        pass
                
                target_date_str = next_date.strftime('%Y-%m-%d')
                if not self.db.expense_exists_on_date(
                    account, target_date_str,
                    recurring['payee'], recurring['amount']
                ):
                    expense = {
                        'amount': recurring['amount'],
                        'payee': recurring['payee'],
                        'note': recurring.get('note', ''),
                        'date': next_date.strftime('%Y-%m-%d %H:%M'),
                        'is_income': recurring.get('is_income', False),
                        'recurring_id': recurring.get('id')
                    }
                    self.db.add_expense(account, expense)
                
                # Calculate next date based on frequency
                next_date = self._add_frequency(next_date, frequency)
            
            # Update last_generated timestamp
            self.db.update_recurring(
                recurring['id'], last_generated=current_date.isoformat()
            )

    def _add_frequency(self, date_obj, frequency):
        """Add frequency duration to a date"""
        from datetime import timedelta
        
        if frequency == 'daily':
            return date_obj + timedelta(days=1)
        elif frequency == 'weekly':
            return date_obj + timedelta(weeks=1)
        elif frequency == 'monthly':
            # Add one month
            if date_obj.month == 12:
                return date_obj.replace(year=date_obj.year + 1, month=1)
            else:
                return date_obj.replace(month=date_obj.month + 1)
        elif frequency == 'yearly':
            return date_obj.replace(year=date_obj.year + 1)
        else:
            # Try to parse as custom interval (number of days)
            try:
                days = int(frequency)
                return date_obj + timedelta(days=days)
            except:
                return date_obj + timedelta(days=1)  # Default to daily

    def on_add_expense(self, widget):
        """Handle adding a new expense"""
        amount_text = self.amount_entry.get_text().strip()
        payee_text = self.payee_entry.get_text().strip()
        note_text = self.note_entry.get_text().strip()
        is_income = self.income_switch.get_active()

        if not amount_text or not payee_text:
            return

        try:
            # Parse amount (accept both comma and dot as decimal separator)
            amount = float(amount_text.replace(',', '.'))
            # For expenses, make amount negative; for income, keep positive
            if not is_income:
                amount = -amount

            # Create expense entry
            expense = {
                'amount': amount,
                'payee': payee_text,
                'note': note_text,
                'date': datetime.now().strftime('%Y-%m-%d %H:%M'),
                'is_income': is_income
            }

            # Save to database
            self.db.add_expense(self.current_account, expense)

            # Update autocomplete suggestions
            self.update_payee_suggestions()

            # Update UI
            self.update_expense_list()
            self.update_total()

            # Clear inputs
            self.amount_entry.set_text('')
            self.payee_entry.set_text('')
            self.note_entry.set_text('')
            self.income_switch.set_active(False)
            self.amount_entry.grab_focus()

        except ValueError:
            # Invalid number format
            dialog = Adw.MessageDialog.new(self)
            dialog.set_heading("Invalid Amount")
            dialog.set_body("Please enter a valid number for the amount.")
            dialog.add_response("ok", "OK")
            dialog.present()

    def update_expense_list(self):
        """Rebuild the expense list with the first page of results."""
        # Clear existing items
        while True:
            row = self.expense_list.get_row_at_index(0)
            if row is None:
                break
            self.expense_list.remove(row)

        self.displayed_count = 0
        search = self.search_query or None

        # Load first page (already newest-first from DB)
        expenses = self.db.get_expenses(
            self.current_account,
            limit=self.page_size, offset=0,
            search=search,
        )
        total = self.db.count_expenses(self.current_account, search=search)

        for expense in expenses:
            self.expense_list.append(self.create_expense_row(expense))
        self.displayed_count = len(expenses)

        # "Show more" row if there are additional results
        if self.displayed_count < total:
            self._append_show_more_row(total)

    def _append_show_more_row(self, total):
        """Add a 'Show more' button row at the bottom of the list."""
        remaining = total - self.displayed_count
        row = Adw.ActionRow()
        row.set_title(f"Show more ({remaining} remaining)")
        row.set_activatable(True)
        row.connect('activated', self._on_show_more, total)
        self.expense_list.append(row)

    def _on_show_more(self, row, total):
        """Load the next page of expenses."""
        # Remove the "Show more" row
        self.expense_list.remove(row)

        search = self.search_query or None
        expenses = self.db.get_expenses(
            self.current_account,
            limit=self.page_size,
            offset=self.displayed_count,
            search=search,
        )

        for expense in expenses:
            self.expense_list.append(self.create_expense_row(expense))
        self.displayed_count += len(expenses)

        if self.displayed_count < total:
            self._append_show_more_row(total)

    def create_expense_row(self, expense):
        """Create a list row for an expense"""
        expense_id = expense['id']
        row = Adw.ActionRow()
        # Escape ampersands for safe display in GTK labels
        payee_text = expense['payee'].replace('&', '&amp;')
        row.set_title(payee_text)
        
        # Build subtitle with note and date
        note = expense.get('note', '').replace('&', '&amp;')
        if note:
            subtitle = f"{note} • {expense['date']}"
        else:
            subtitle = expense['date']
        
        # Check if this expense is recurring
        recurring_id = expense.get('recurring_id')
        if recurring_id:
            subtitle = f"↻ {subtitle}"
        
        row.set_subtitle(subtitle)

        # Amount label - show absolute value with appropriate sign
        amount = expense['amount']
        is_income = expense.get('is_income', False)
        
        # Format the amount - for expenses show as negative, for income show as positive
        if is_income:
            amount_text = f"+{abs(amount):.2f} €"
        else:
            amount_text = f"-{abs(amount):.2f} €"
        
        amount_label = Gtk.Label()
        amount_label.set_text(amount_text)
        amount_label.add_css_class('title-3')
        
        # Color code: green for income, red for expenses
        if is_income:
            amount_label.add_css_class('success')
        else:
            amount_label.add_css_class('error')

        # Recurring button - either "Make Recurring" or "Stop Recurring"
        recurring_button = Gtk.Button()
        recurring_button.set_valign(Gtk.Align.CENTER)
        recurring_button.add_css_class('flat')
        
        if recurring_id:
            recurring_button.set_icon_name('window-close-symbolic')
            recurring_button.set_tooltip_text('Stop recurring')
            recurring_button.connect('clicked', self.on_stop_recurring, expense_id)
            
            # Add edit button for recurring expenses
            edit_button = Gtk.Button()
            edit_button.set_icon_name('document-edit-symbolic')
            edit_button.set_tooltip_text('Edit recurring')
            edit_button.set_valign(Gtk.Align.CENTER)
            edit_button.add_css_class('flat')
            edit_button.connect('clicked', self.on_edit_recurring, expense_id)
            row.add_suffix(edit_button)
        else:
            recurring_button.set_icon_name('view-refresh-symbolic')
            recurring_button.set_tooltip_text('Make recurring')
            recurring_button.connect('clicked', self.on_make_recurring, expense_id)
        
        row.add_suffix(recurring_button)

        # Delete button
        delete_button = Gtk.Button()
        delete_button.set_icon_name('user-trash-symbolic')
        delete_button.set_valign(Gtk.Align.CENTER)
        delete_button.add_css_class('flat')
        delete_button.connect('clicked', self.on_delete_expense, expense_id)

        # Add to row
        row.add_suffix(amount_label)
        row.add_suffix(delete_button)

        return row

    def on_delete_expense(self, button, expense_id):
        """Handle deleting an expense"""
        expense = self.db.get_expense_by_id(expense_id)
        if expense is None:
            return

        # If this expense is recurring, remove the recurring definition
        if expense.get('recurring_id'):
            self.db.delete_recurring(expense['recurring_id'])

        self.db.delete_expense(expense_id)
        self.update_expense_list()
        self.update_total()
        self.update_payee_suggestions()

    def on_stop_recurring(self, button, expense_id):
        """Handle stopping a recurring expense"""
        expense = self.db.get_expense_by_id(expense_id)
        if expense and expense.get('recurring_id'):
            recurring_id = expense['recurring_id']

            # Remove from recurring definitions
            self.db.delete_recurring(recurring_id)

            # Remove recurring_id from ALL expenses with this recurring_id
            self.db.clear_recurring_from_expenses(recurring_id)

            self.update_expense_list()

    def on_make_recurring(self, button, expense_id):
        """Show dialog to make an expense recurring"""
        expense = self.db.get_expense_by_id(expense_id)
        if expense is None:
            return
        
        # Create a dialog for recurring setup
        dialog = Adw.MessageDialog.new(self)
        dialog.set_heading("Make Recurring")
        dialog.set_body(f"Set up recurring for {expense['payee']}?")
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("ok", "Create")
        dialog.set_default_response("ok")
        dialog.set_response_appearance("ok", Adw.ResponseAppearance.SUGGESTED)
        
        # Create frequency selector using ComboBoxText
        frequency_combo = Gtk.ComboBoxText()
        for freq in ['Daily', 'Weekly', 'Monthly', 'Yearly']:
            frequency_combo.append_text(freq)
        frequency_combo.set_active(2)  # Default to Monthly
        
        # Create end date entry
        end_date_entry = Gtk.Entry()
        end_date_entry.set_placeholder_text("YYYY-MM-DD (optional)")
        
        # Create a box for inputs
        input_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        input_box.set_spacing(12)
        input_box.set_margin_top(12)
        input_box.append(Gtk.Label(label="Frequency:", xalign=0))
        input_box.append(frequency_combo)
        input_box.append(Gtk.Label(label="End Date (optional):", xalign=0))
        input_box.append(end_date_entry)
        
        dialog.set_extra_child(input_box)
        
        def on_response(dialog, response):
            if response == "ok":
                # Get selected frequency
                frequency_index = frequency_combo.get_active()
                frequencies = ['daily', 'weekly', 'monthly', 'yearly']
                frequency = frequencies[frequency_index] if frequency_index >= 0 else 'monthly'
                
                # Get end date
                end_date = end_date_entry.get_text().strip()
                
                # Create recurring definition
                # Create recurring definition
                recurring = {
                    'id': str(uuid.uuid4()),
                    'amount': expense['amount'],
                    'payee': expense['payee'],
                    'note': expense.get('note', ''),
                    'is_income': expense.get('is_income', False),
                    'frequency': frequency,
                    'start_date': expense['date'],
                    'end_date': end_date if end_date else None,
                    'last_generated': expense['date'],
                    'account': self.current_account
                }
                
                self.db.add_recurring(self.current_account, recurring)
                
                # Mark the original expense
                self.db.set_expense_recurring(expense_id, recurring['id'])
                
                self.update_expense_list()
                
                # Show confirmation
                confirm_dialog = Adw.MessageDialog.new(self)
                confirm_dialog.set_heading("Recurring Created")
                confirm_dialog.set_body(f"{expense['payee']} is now recurring ({frequency.capitalize()})")
                confirm_dialog.add_response("ok", "OK")
                confirm_dialog.present()
        
        dialog.connect('response', on_response)
        dialog.present()
    
    def on_edit_recurring(self, button, expense_id):
        """Show dialog to edit a recurring expense interval"""
        expense = self.db.get_expense_by_id(expense_id)
        if expense is None:
            return

        recurring_id = expense.get('recurring_id')
        if not recurring_id:
            return
        
        # Find the recurring definition
        recurring = self.db.get_recurring_by_id(recurring_id)
        if not recurring:
            return
        
        # Create a dialog for editing recurring setup
        dialog = Adw.MessageDialog.new(self)
        dialog.set_heading("Edit Recurring")
        dialog.set_body(f"Change interval for {expense['payee']}?")
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("ok", "Update")
        dialog.set_default_response("ok")
        dialog.set_response_appearance("ok", Adw.ResponseAppearance.SUGGESTED)
        
        # Create frequency selector using ComboBoxText
        frequency_combo = Gtk.ComboBoxText()
        for freq in ['Daily', 'Weekly', 'Monthly', 'Yearly']:
            frequency_combo.append_text(freq)
        
        # Set current frequency
        current_frequency = recurring.get('frequency', 'monthly').capitalize()
        for i, freq in enumerate(['Daily', 'Weekly', 'Monthly', 'Yearly']):
            if freq == current_frequency:
                frequency_combo.set_active(i)
                break
        
        # Create end date entry
        end_date_entry = Gtk.Entry()
        end_date_entry.set_placeholder_text("YYYY-MM-DD (optional)")
        if recurring.get('end_date'):
            end_date_entry.set_text(recurring['end_date'])
        
        # Create a box for inputs
        input_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        input_box.set_spacing(12)
        input_box.set_margin_top(12)
        input_box.append(Gtk.Label(label="Frequency:", xalign=0))
        input_box.append(frequency_combo)
        input_box.append(Gtk.Label(label="End Date (optional):", xalign=0))
        input_box.append(end_date_entry)
        
        dialog.set_extra_child(input_box)
        
        def on_response(dialog, response):
            if response == "ok":
                # Get selected frequency
                frequency_index = frequency_combo.get_active()
                frequencies = ['daily', 'weekly', 'monthly', 'yearly']
                frequency = frequencies[frequency_index] if frequency_index >= 0 else 'monthly'
                
                # Get end date
                end_date = end_date_entry.get_text().strip()
                
                # Update recurring definition (does not affect past expenses)
                self.db.update_recurring(
                    recurring_id,
                    frequency=frequency,
                    end_date=end_date if end_date else None
                )
                
                self.update_expense_list()
                
                # Show confirmation
                confirm_dialog = Adw.MessageDialog.new(self)
                confirm_dialog.set_heading("Recurring Updated")
                confirm_dialog.set_body(f"{expense['payee']} interval changed to {frequency.capitalize()}")
                confirm_dialog.add_response("ok", "OK")
                confirm_dialog.present()
        
        dialog.connect('response', on_response)
        dialog.present()

    def update_total(self):
        """Update the total amount display"""
        total = self.db.get_account_total(self.current_account)
        self.total_label.set_text(f"{total:.2f} €")

    def on_search_changed(self, search_entry):
        """Handle search query changes"""
        self.search_query = search_entry.get_text()
        self.update_expense_list()

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
        except:
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
            return os.path.join(tmp_dir, backup_name)

    def import_sqlite_database(self, db_path):
        """Import data from SQLite database"""
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
                except:
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

            # Use SQLite's online-backup API for a consistent snapshot
            dst = sqlite3.connect(dest_path)
            self.db.conn.backup(dst)
            dst.close()

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
            # Restore from the selected file using SQLite backup API
            src = sqlite3.connect(path)
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
