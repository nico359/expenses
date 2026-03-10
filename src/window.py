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
import sqlite3
from datetime import datetime

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
    search_entry = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Data storage
        self.data = {
            'accounts': ['Default'],
            'current_account': 'Default',
            'expenses': {},  # {account_name: [expenses]}
            'recurring_expenses': []  # List of recurring expense definitions
        }
        self.data_file = os.path.join(GLib.get_user_data_dir(), 'expenses.json')
        self.search_query = ''  # Track current search query

        # Load existing data
        self.load_data()
        
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
        self.search_entry.connect('search-changed', self.on_search_changed)

        # Setup import/export actions
        import_action = Gio.SimpleAction.new("import-db", None)
        import_action.connect("activate", self.on_import_database)
        self.add_action(import_action)
        
        export_action = Gio.SimpleAction.new("export-json", None)
        export_action.connect("activate", self.on_export_json)
        self.add_action(export_action)
        
        import_json_action = Gio.SimpleAction.new("import-json", None)
        import_json_action.connect("activate", self.on_import_json)
        self.add_action(import_json_action)

        # Update UI
        self.update_expense_list()
        self.update_total()

    def setup_payee_autocomplete(self):
        """Setup autocomplete for payee entry"""
        # Create a scrollable list for suggestions
        suggestion_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        scrollable = Gtk.ScrolledWindow()
        scrollable.set_max_content_height(250)
        scrollable.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        
        self.payee_list = Gtk.ListBox()
        self.payee_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.payee_list.connect('row-activated', self.on_payee_selected)
        
        scrollable.set_child(self.payee_list)
        suggestion_box.append(scrollable)
        
        # Create a popover with suggestions
        self.payee_popover = Gtk.Popover()
        self.payee_popover.set_child(suggestion_box)
        self.payee_popover.set_position(Gtk.PositionType.BOTTOM)
        self.payee_popover.set_has_arrow(False)
        
        # Store all unique payees for filtering
        self.all_payees = []
        
        # Connect to payee entry changes
        self.payee_entry.connect('notify::text', self.on_payee_changed)
        self.update_payee_suggestions()

    def update_payee_suggestions(self):
        """Update autocomplete suggestions based on existing payees"""
        payees = set()

        # Collect all unique payees from all accounts
        for account_expenses in self.data['expenses'].values():
            for expense in account_expenses:
                payees.add(expense['payee'])

        # Store all payees
        self.all_payees = sorted(payees)

    def on_payee_changed(self, entry, param):
        """Handle payee entry text changes to show suggestions"""
        text = entry.get_text().strip()
        
        # If text is too short, hide popover
        if len(text) < 1:
            self.payee_popover.popdown()
            return
        
        # Filter suggestions based on text
        text_lower = text.lower()
        matching_payees = [p for p in self.all_payees if text_lower in p.lower()]
        
        # Clear and rebuild list
        while self.payee_list.get_first_child():
            self.payee_list.remove(self.payee_list.get_first_child())
        
        # Add matching suggestions
        for payee in matching_payees:
            label = Gtk.Label(label=payee, xalign=0)
            label.set_margin_start(12)
            label.set_margin_end(12)
            label.set_margin_top(8)
            label.set_margin_bottom(8)
            row = Gtk.ListBoxRow(child=label)
            self.payee_list.append(row)
        
        # Show popover if there are matches
        if matching_payees:
            self.payee_popover.set_parent(entry)
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
        # Create string list including existing accounts + add new option
        self.account_list = Gtk.StringList()
        for account in self.data['accounts']:
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
            index = self.data['accounts'].index(self.data['current_account'])
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
        if selected != Gtk.INVALID_LIST_POSITION:
            # Check if "Add Account" was selected
            if selected == len(self.data['accounts']):
                # Reset to previous selection and show add account dialog
                try:
                    prev_index = self.data['accounts'].index(self.data['current_account'])
                    self.account_dropdown.set_selected(prev_index)
                except ValueError:
                    self.account_dropdown.set_selected(0)
                self.on_add_account()
            else:
                # Normal account selection
                self.data['current_account'] = self.data['accounts'][selected]
                self.save_data()
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
            if account_name and account_name not in self.data['accounts']:
                self.data['accounts'].append(account_name)
                self.data['expenses'][account_name] = []
                self.save_data()
                
                # Rebuild the dropdown with new account
                self.setup_account_dropdown()
                
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
                    if 'recurring_expenses' in loaded_data:
                        self.data['recurring_expenses'] = loaded_data['recurring_expenses']
            except:
                pass

        # Ensure current account exists in accounts list
        if self.data['current_account'] not in self.data['accounts']:
            self.data['current_account'] = self.data['accounts'][0]

        # Ensure all accounts have expense lists
        for account in self.data['accounts']:
            if account not in self.data['expenses']:
                self.data['expenses'][account] = []
        
        # Ensure recurring_expenses list exists
        if 'recurring_expenses' not in self.data:
            self.data['recurring_expenses'] = []

    def save_data(self):
        """Save data to JSON file"""
        try:
            os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
            with open(self.data_file, 'w') as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            print(f"Error saving data: {e}")

    def process_recurring_expenses(self):
        """Check and generate missing recurring expenses on startup"""
        from datetime import timedelta
        
        for recurring in self.data.get('recurring_expenses', []):
            # Skip if no account specified
            if 'account' not in recurring:
                continue
                
            account = recurring['account']
            if account not in self.data['expenses']:
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
                        # Try parsing as ISO datetime first, then as date
                        try:
                            end_date = datetime.fromisoformat(recurring['end_date'])
                        except:
                            end_date = datetime.fromisoformat(recurring['end_date'] + 'T23:59:59')
                        if next_date.date() > end_date.date():
                            break
                    except:
                        pass
                
                # Skip if entry already exists on this date
                if not self._expense_exists_on_date(account, next_date, recurring):
                    # Create the expense entry
                    expense = {
                        'amount': recurring['amount'],
                        'payee': recurring['payee'],
                        'note': recurring.get('note', ''),
                        'date': next_date.strftime('%Y-%m-%d %H:%M'),
                        'is_income': recurring.get('is_income', False),
                        'recurring_id': recurring.get('id')
                    }
                    self.data['expenses'][account].append(expense)
                
                # Calculate next date based on frequency
                next_date = self._add_frequency(next_date, frequency)
            
            # Update last_generated timestamp
            recurring['last_generated'] = current_date.isoformat()
        
        # Save if we generated any new expenses
        if self.data.get('recurring_expenses'):
            self.save_data()

    def _expense_exists_on_date(self, account, target_date, recurring):
        """Check if an expense from a recurring definition already exists on a given date"""
        target_date_str = target_date.strftime('%Y-%m-%d')
        for expense in self.data['expenses'].get(account, []):
            expense_date_str = expense['date'].split()[0]
            if expense_date_str == target_date_str and \
               expense['payee'] == recurring['payee'] and \
               expense['amount'] == recurring['amount']:
                return True
        return False

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
        """Update the expense list display"""
        # Clear existing items
        while True:
            row = self.expense_list.get_row_at_index(0)
            if row is None:
                break
            self.expense_list.remove(row)

        # Get expenses for current account
        expenses = self.get_current_expenses()

        # Filter by search query if present
        if self.search_query:
            query_lower = self.search_query.lower()
            expenses = [e for e in expenses if query_lower in e['payee'].lower() or query_lower in e.get('note', '').lower()]

        # Add expenses in reverse order (newest first)
        for i, expense in enumerate(reversed(expenses)):
            row = self.create_expense_row(expense, len(expenses) - 1 - i)
            self.expense_list.append(row)

    def create_expense_row(self, expense, index):
        """Create a list row for an expense"""
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
            subtitle = f"🔁 {subtitle}"
        
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

        # Make recurring button (if not already recurring)
        if not recurring_id:
            recurring_button = Gtk.Button()
            recurring_button.set_icon_name('media-repeat-symbolic')
            recurring_button.set_valign(Gtk.Align.CENTER)
            recurring_button.add_css_class('flat')
            recurring_button.set_tooltip_text('Make recurring')
            recurring_button.connect('clicked', self.on_make_recurring, index)
            row.add_suffix(recurring_button)

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

    def on_make_recurring(self, button, index):
        """Show dialog to make an expense recurring"""
        expenses = self.get_current_expenses()
        if not (0 <= index < len(expenses)):
            return
        
        expense = expenses[index]
        
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
                import uuid
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
                    'account': self.data['current_account']
                }
                
                self.data['recurring_expenses'].append(recurring)
                
                # Mark the original expense
                expense['recurring_id'] = recurring['id']
                
                self.save_data()
                self.update_expense_list()
                
                # Show confirmation
                confirm_dialog = Adw.MessageDialog.new(self)
                confirm_dialog.set_heading("Recurring Created")
                confirm_dialog.set_body(f"✓ {expense['payee']} is now recurring ({frequency.capitalize()})")
                confirm_dialog.add_response("ok", "OK")
                confirm_dialog.present()
        
        dialog.connect('response', on_response)
        dialog.present()

    def update_total(self):
        """Update the total amount display"""
        expenses = self.get_current_expenses()
        total = sum(expense['amount'] for expense in expenses)
        self.total_label.set_text(f"{total:.2f} €")

    def on_search_changed(self, search_entry):
        """Handle search query changes"""
        self.search_query = search_entry.get_text()
        self.update_expense_list()

    def on_import_database(self, action, param):
        """Show file chooser for importing SQLite database"""
        dialog = Gtk.FileDialog()
        dialog.set_title("Import Database")
        dialog.set_modal(True)
        
        # Set initial folder to home directory
        home_dir = GLib.get_home_dir()
        try:
            initial_folder = Gio.File.new_for_path(home_dir)
            dialog.set_initial_folder(initial_folder)
        except:
            pass
        
        # Create filter for SQLite databases
        filters = Gio.ListStore.new(Gtk.FileFilter)
        all_filter = Gtk.FileFilter()
        all_filter.set_name("All Files")
        all_filter.add_pattern("*")
        filters.append(all_filter)
        
        db_filter = Gtk.FileFilter()
        db_filter.set_name("SQLite Databases")
        db_filter.add_pattern("BACKUP")
        db_filter.add_pattern("*.db")
        db_filter.add_pattern("*.sqlite")
        filters.append(db_filter)
        
        dialog.set_filters(filters)
        dialog.open(self, None, self.on_import_file_selected)

    def on_import_file_selected(self, dialog, result):
        """Handle file selection for import"""
        try:
            file = dialog.open_finish(result)
            path = file.get_path()
            
            # Import the database
            accounts_imported, transactions_imported = self.import_sqlite_database(path)
            
            # Show success message
            success_dialog = Adw.MessageDialog.new(self)
            success_dialog.set_heading("Import Successful")
            success_dialog.set_body(f"Imported {accounts_imported} account(s) and {transactions_imported} transaction(s)")
            success_dialog.add_response("ok", "OK")
            success_dialog.set_response_appearance("ok", Adw.ResponseAppearance.DEFAULT)
            success_dialog.connect('response', lambda d, r: self.on_import_complete())
            success_dialog.present()
            
        except GLib.Error as e:
            # Show error message
            error_dialog = Adw.MessageDialog.new(self)
            error_dialog.set_heading("Import Failed")
            error_dialog.set_body(f"Could not open file: {str(e)}")
            error_dialog.add_response("ok", "OK")
            error_dialog.present()

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
            
            # Replace all data with imported data
            self.data = {
                'accounts': account_list,
                'current_account': account_list[0] if account_list else 'Default',
                'expenses': expenses_data
            }
            
            # Save the new data
            self.save_data()
            
            # Return counts for the success message
            total_transactions = sum(len(expenses) for expenses in expenses_data.values())
            return len(account_list), total_transactions
            
        except Exception as e:
            print(f"Error importing database: {e}")
            raise

    def on_import_complete(self):
        """Handle import completion - refresh UI"""
        # Refresh the UI
        self.setup_account_dropdown()
        self.update_expense_list()
        self.update_total()
        self.update_payee_suggestions()

    def on_export_json(self, action, param):
        """Export current data to JSON file with timestamp"""
        dialog = Gtk.FileChooserDialog(
            title="Export Expenses",
            transient_for=self,
            action=Gtk.FileChooserAction.SAVE,
        )
        dialog.add_buttons(
            "_Cancel", Gtk.ResponseType.CANCEL,
            "_Save", Gtk.ResponseType.OK
        )

        # Set default filename with timestamp
        now = datetime.now()
        default_filename = f"expenses-backup-{now.strftime('%Y-%m-%d')}.json"
        dialog.set_current_name(default_filename)

        # Add JSON filter
        filter = Gtk.FileFilter()
        filter.set_name("JSON files")
        filter.add_pattern("*.json")
        dialog.add_filter(filter)

        dialog.connect('response', self.on_export_file_selected)
        dialog.present()

    def on_export_file_selected(self, dialog, response):
        """Handle export file selection"""
        if response != Gtk.ResponseType.OK:
            dialog.close()
            return

        file_path = dialog.get_file().get_path()
        dialog.close()

        try:
            # Save current data to selected file
            with open(file_path, 'w') as f:
                json.dump(self.data, f, indent=2)

            # Show success dialog
            success_dialog = Adw.MessageDialog.new(self)
            success_dialog.set_heading("Export Successful")
            success_dialog.set_body(f"Data exported to:\n{file_path}")
            success_dialog.add_response("ok", "OK")
            success_dialog.present()

        except Exception as e:
            error_dialog = Adw.MessageDialog.new(self)
            error_dialog.set_heading("Export Failed")
            error_dialog.set_body(f"Could not save file: {str(e)}")
            error_dialog.add_response("ok", "OK")
            error_dialog.present()

    def on_import_json(self, action, param):
        """Import data from JSON file"""
        dialog = Gtk.FileChooserDialog(
            title="Import Expenses from JSON",
            transient_for=self,
            action=Gtk.FileChooserAction.OPEN,
        )
        dialog.add_buttons(
            "_Cancel", Gtk.ResponseType.CANCEL,
            "_Open", Gtk.ResponseType.OK
        )

        # Add JSON filter
        filter = Gtk.FileFilter()
        filter.set_name("JSON files")
        filter.add_pattern("*.json")
        dialog.add_filter(filter)

        dialog.connect('response', self.on_import_json_file_selected)
        dialog.present()

    def on_import_json_file_selected(self, dialog, response):
        """Handle JSON import file selection"""
        if response != Gtk.ResponseType.OK:
            dialog.close()
            return

        file_path = dialog.get_file().get_path()
        dialog.close()

        try:
            # Confirm before replacing data
            confirm_dialog = Adw.MessageDialog.new(self)
            confirm_dialog.set_heading("Replace Existing Data?")
            confirm_dialog.set_body("This will replace all current expenses. Continue?")
            confirm_dialog.add_response("cancel", "Cancel")
            confirm_dialog.add_response("import", "Import")
            confirm_dialog.set_response_appearance("import", Adw.ResponseAppearance.DESTRUCTIVE)
            confirm_dialog.connect('response', self.on_json_import_confirmed, file_path)
            confirm_dialog.present()

        except Exception as e:
            error_dialog = Adw.MessageDialog.new(self)
            error_dialog.set_heading("Import Failed")
            error_dialog.set_body(f"Could not open file: {str(e)}")
            error_dialog.add_response("ok", "OK")
            error_dialog.present()

    def on_json_import_confirmed(self, dialog, response, file_path):
        """Handle JSON import confirmation"""
        if response != "import":
            return

        try:
            # Load JSON data
            with open(file_path, 'r') as f:
                imported_data = json.load(f)

            # Validate structure
            if not isinstance(imported_data, dict) or 'accounts' not in imported_data or 'expenses' not in imported_data:
                raise ValueError("Invalid JSON format")

            # Replace data
            self.data = imported_data

            # Ensure current_account exists
            if 'current_account' not in self.data:
                self.data['current_account'] = self.data['accounts'][0] if self.data['accounts'] else 'Default'

            # Save to app storage
            self.save_data()

            # Refresh UI
            self.on_import_complete()

            # Show success dialog
            total_expenses = sum(len(expenses) for expenses in self.data['expenses'].values())
            success_dialog = Adw.MessageDialog.new(self)
            success_dialog.set_heading("Import Successful")
            success_dialog.set_body(f"Imported {len(self.data['accounts'])} account(s) with {total_expenses} expense(s)")
            success_dialog.add_response("ok", "OK")
            success_dialog.present()

        except Exception as e:
            error_dialog = Adw.MessageDialog.new(self)
            error_dialog.set_heading("Import Failed")
            error_dialog.set_body(f"Could not import file: {str(e)}")
            error_dialog.add_response("ok", "OK")
            error_dialog.present()
