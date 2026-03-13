# expenses.py
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

import uuid
from datetime import datetime

from gi.repository import Adw, Gtk


class ExpensesMixin:
    """Expense CRUD, recurring logic, and list rendering."""

    def process_recurring_expenses(self):
        """Check and generate missing recurring expenses on startup"""
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
                except (ValueError, TypeError):
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
                        except ValueError:
                            end_date = datetime.fromisoformat(recurring['end_date'] + 'T23:59:59')
                        if next_date.date() > end_date.date():
                            break
                    except (ValueError, TypeError):
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
        import calendar

        if frequency == 'daily':
            return date_obj + timedelta(days=1)
        elif frequency == 'weekly':
            return date_obj + timedelta(weeks=1)
        elif frequency == 'monthly':
            next_month = date_obj.month % 12 + 1
            next_year = date_obj.year + (1 if date_obj.month == 12 else 0)
            max_day = calendar.monthrange(next_year, next_month)[1]
            return date_obj.replace(
                year=next_year, month=next_month,
                day=min(date_obj.day, max_day),
            )
        elif frequency == 'yearly':
            # Handle Feb 29 in leap years
            max_day = calendar.monthrange(date_obj.year + 1, date_obj.month)[1]
            return date_obj.replace(
                year=date_obj.year + 1,
                day=min(date_obj.day, max_day),
            )
        else:
            try:
                days = int(frequency)
                return date_obj + timedelta(days=days)
            except (ValueError, TypeError):
                return date_obj + timedelta(days=1)

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
