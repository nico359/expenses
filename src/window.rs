/* window.rs
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
use adw::subclass::prelude::*;
use gtk::{gio, glib};

use std::cell::{OnceCell, RefCell};

use crate::db::Database;

mod imp {
    use super::*;

    #[derive(Debug, gtk::CompositeTemplate)]
    #[template(resource = "/io/github/nico359/expenses/window.ui")]
    pub struct ExpensesWindow {
        #[template_child]
        pub account_dropdown: TemplateChild<gtk::DropDown>,
        #[template_child]
        pub delete_account_button: TemplateChild<gtk::Button>,
        #[template_child]
        pub amount_entry: TemplateChild<adw::EntryRow>,
        #[template_child]
        pub payee_entry: TemplateChild<adw::EntryRow>,
        #[template_child]
        pub note_entry: TemplateChild<adw::EntryRow>,
        #[template_child]
        pub income_switch: TemplateChild<adw::SwitchRow>,
        #[template_child]
        pub add_button: TemplateChild<gtk::Button>,
        #[template_child]
        pub total_label: TemplateChild<gtk::Label>,
        #[template_child]
        pub search_entry: TemplateChild<gtk::SearchEntry>,
        #[template_child]
        pub expense_list: TemplateChild<gtk::ListBox>,

        pub db: RefCell<Option<Database>>,
        pub current_account_id: RefCell<i64>,
        pub current_offset: RefCell<i64>,
        pub all_payees: RefCell<Vec<String>>,
        pub payee_popover: OnceCell<gtk::Popover>,
        pub payee_suggestion_list: OnceCell<gtk::ListBox>,
    }

    impl Default for ExpensesWindow {
        fn default() -> Self {
            Self {
                account_dropdown: TemplateChild::default(),
                delete_account_button: TemplateChild::default(),
                amount_entry: TemplateChild::default(),
                payee_entry: TemplateChild::default(),
                note_entry: TemplateChild::default(),
                income_switch: TemplateChild::default(),
                add_button: TemplateChild::default(),
                total_label: TemplateChild::default(),
                search_entry: TemplateChild::default(),
                expense_list: TemplateChild::default(),
                db: RefCell::new(None),
                current_account_id: RefCell::new(0),
                current_offset: RefCell::new(0),
                all_payees: RefCell::new(Vec::new()),
                payee_popover: OnceCell::new(),
                payee_suggestion_list: OnceCell::new(),
            }
        }
    }

    #[glib::object_subclass]
    impl ObjectSubclass for ExpensesWindow {
        const NAME: &'static str = "ExpensesWindow";
        type Type = super::ExpensesWindow;
        type ParentType = adw::ApplicationWindow;

        fn class_init(klass: &mut Self::Class) {
            klass.bind_template();
        }

        fn instance_init(obj: &glib::subclass::InitializingObject<Self>) {
            obj.init_template();
        }
    }

    impl ObjectImpl for ExpensesWindow {
        fn constructed(&self) {
            self.parent_constructed();
            let obj = self.obj();
            obj.init_db();
            obj.setup_actions();
            obj.setup_accounts();
            obj.setup_payee_autocomplete();
            obj.setup_signals();
            obj.process_recurring_expenses();
            obj.refresh_expenses();
        }
    }

    impl WidgetImpl for ExpensesWindow {}
    impl WindowImpl for ExpensesWindow {}
    impl ApplicationWindowImpl for ExpensesWindow {}
    impl AdwApplicationWindowImpl for ExpensesWindow {}
}

glib::wrapper! {
    pub struct ExpensesWindow(ObjectSubclass<imp::ExpensesWindow>)
        @extends gtk::Widget, gtk::Window, gtk::ApplicationWindow, adw::ApplicationWindow,
        @implements gio::ActionGroup, gio::ActionMap;
}

impl ExpensesWindow {
    pub fn new<P: IsA<gtk::Application>>(application: &P) -> Self {
        glib::Object::builder()
            .property("application", application)
            .build()
    }

    pub(crate) fn init_db(&self) {
        match Database::new() {
            Ok(db) => {
                *self.imp().db.borrow_mut() = Some(db);
            }
            Err(e) => {
                eprintln!("Failed to initialize database: {}", e);
            }
        }
    }

    pub(crate) fn db(&self) -> std::cell::Ref<'_, Database> {
        std::cell::Ref::map(self.imp().db.borrow(), |opt| opt.as_ref().unwrap())
    }

    fn setup_actions(&self) {
        let import_myexpenses = gio::ActionEntry::builder("import-myexpenses")
            .activate(glib::clone!(
                #[weak(rename_to = window)]
                self,
                move |_, _, _| { window.on_import_myexpenses(); }
            ))
            .build();
        let export_myexpenses = gio::ActionEntry::builder("export-myexpenses")
            .activate(glib::clone!(
                #[weak(rename_to = window)]
                self,
                move |_, _, _| { window.on_export_myexpenses(); }
            ))
            .build();
        let export_db = gio::ActionEntry::builder("export-db")
            .activate(glib::clone!(
                #[weak(rename_to = window)]
                self,
                move |_, _, _| { window.on_export_db(); }
            ))
            .build();
        let import_db = gio::ActionEntry::builder("import-db")
            .activate(glib::clone!(
                #[weak(rename_to = window)]
                self,
                move |_, _, _| { window.on_import_db(); }
            ))
            .build();
        self.add_action_entries([import_myexpenses, export_myexpenses, export_db, import_db]);
    }

    // --- Account Management ---

    pub(crate) fn setup_accounts(&self) {
        let accounts = self.db().get_accounts().unwrap_or_default();
        let mut names: Vec<String> = accounts.iter().map(|a| a.name.clone()).collect();
        names.push("+ Add Account".to_string());

        let model = gtk::StringList::new(&names.iter().map(|s| s.as_str()).collect::<Vec<_>>());
        self.imp().account_dropdown.set_model(Some(&model));

        // Restore last selected account
        let current_name = self.db().get_setting("current_account")
            .unwrap_or_else(|| accounts.first().map(|a| a.name.clone()).unwrap_or_default());

        let selected_idx = accounts.iter().position(|a| a.name == current_name).unwrap_or(0);
        if let Some(account) = accounts.get(selected_idx) {
            *self.imp().current_account_id.borrow_mut() = account.id;
            self.imp().account_dropdown.set_selected(selected_idx as u32);
        }

        // Connect dropdown changed signal
        self.imp().account_dropdown.connect_selected_notify(glib::clone!(
            #[weak(rename_to = window)]
            self,
            move |dropdown| {
                window.on_account_changed(dropdown);
            }
        ));

        // Connect delete account button
        self.imp().delete_account_button.connect_clicked(glib::clone!(
            #[weak(rename_to = window)]
            self,
            move |_| {
                window.on_delete_account();
            }
        ));
    }

    fn on_account_changed(&self, dropdown: &gtk::DropDown) {
        let accounts = self.db().get_accounts().unwrap_or_default();
        let idx = dropdown.selected() as usize;

        if idx >= accounts.len() {
            // "Add Account" selected
            self.show_add_account_dialog();
            return;
        }

        if let Some(account) = accounts.get(idx) {
            *self.imp().current_account_id.borrow_mut() = account.id;
            self.db().set_setting("current_account", &account.name).ok();
            self.refresh_expenses();
        }
    }

    fn show_add_account_dialog(&self) {
        let dialog = adw::AlertDialog::builder()
            .heading("New Account")
            .body("Enter a name for the new account:")
            .build();

        dialog.add_response("cancel", "Cancel");
        dialog.add_response("create", "Create");
        dialog.set_response_appearance("create", adw::ResponseAppearance::Suggested);

        let entry = gtk::Entry::builder()
            .placeholder_text("Account name")
            .build();
        dialog.set_extra_child(Some(&entry));

        dialog.choose(self, None::<&gio::Cancellable>, glib::clone!(
            #[weak(rename_to = window)]
            self,
            move |response| {
                if response == "create" {
                    let name = entry.text().trim().to_string();
                    if !name.is_empty() {
                        if let Ok(id) = window.db().add_account(&name) {
                            *window.imp().current_account_id.borrow_mut() = id;
                            window.db().set_setting("current_account", &name).ok();
                            window.setup_accounts();
                            window.refresh_expenses();
                            return;
                        }
                    }
                }
                // Reset dropdown to previous selection
                let account_id = *window.imp().current_account_id.borrow();
                let accounts = window.db().get_accounts().unwrap_or_default();
                if let Some(pos) = accounts.iter().position(|a| a.id == account_id) {
                    window.imp().account_dropdown.set_selected(pos as u32);
                }
            }
        ));
    }

    fn on_delete_account(&self) {
        let count = self.db().account_count().unwrap_or(1);
        if count <= 1 {
            let dialog = adw::AlertDialog::builder()
                .heading("Cannot Delete")
                .body("You must have at least one account.")
                .build();
            dialog.add_response("ok", "OK");
            dialog.present(Some(self));
            return;
        }

        let account_id = *self.imp().current_account_id.borrow();
        let dialog = adw::AlertDialog::builder()
            .heading("Delete Account?")
            .body("This will permanently delete the account and all its expenses.")
            .build();
        dialog.add_response("cancel", "Cancel");
        dialog.add_response("delete", "Delete");
        dialog.set_response_appearance("delete", adw::ResponseAppearance::Destructive);

        dialog.choose(self, None::<&gio::Cancellable>, glib::clone!(
            #[weak(rename_to = window)]
            self,
            move |response| {
                if response == "delete" {
                    window.db().delete_account(account_id).ok();
                    *window.imp().current_account_id.borrow_mut() = 0;
                    window.setup_accounts();
                    window.refresh_expenses();
                }
            }
        ));
    }

    // --- Expense Management ---

    fn setup_payee_autocomplete(&self) {
        let suggestion_list = gtk::ListBox::new();
        suggestion_list.set_selection_mode(gtk::SelectionMode::Single);

        let scrollable = gtk::ScrolledWindow::builder()
            .max_content_height(250)
            .hscrollbar_policy(gtk::PolicyType::Never)
            .vscrollbar_policy(gtk::PolicyType::Automatic)
            .propagate_natural_height(true)
            .child(&suggestion_list)
            .build();

        let popover = gtk::Popover::builder()
            .child(&scrollable)
            .position(gtk::PositionType::Bottom)
            .has_arrow(false)
            .autohide(false)
            .build();
        popover.set_parent(&*self.imp().payee_entry);

        // Select suggestion on row activation — auto-fill amount and note
        suggestion_list.connect_row_activated(glib::clone!(
            #[weak(rename_to = window)]
            self,
            #[weak]
            popover,
            move |_, row| {
                if let Some(label) = row.child().and_then(|c| c.downcast::<gtk::Label>().ok()) {
                    let payee = label.text().to_string();
                    window.imp().payee_entry.set_text(&payee);
                    let len = payee.len() as i32;
                    window.imp().payee_entry.select_region(len, len);

                    // Auto-fill from last expense with this payee
                    let account_id = *window.imp().current_account_id.borrow();
                    if let Ok(Some((amount, note, is_income))) =
                        window.db().get_last_expense_for_payee(account_id, &payee)
                    {
                        let amount_str = if amount.fract() == 0.0 {
                            format!("{:.0}", amount)
                        } else {
                            format!("{:.2}", amount)
                        };
                        window.imp().amount_entry.set_text(&amount_str);
                        window.imp().note_entry.set_text(&note);
                        window.imp().income_switch.set_active(is_income);
                    }
                }
                popover.popdown();
            }
        ));

        // Hide suggestions when entry loses focus
        let focus_controller = gtk::EventControllerFocus::new();
        focus_controller.connect_leave(glib::clone!(
            #[weak]
            popover,
            move |_| { popover.popdown(); }
        ));
        self.imp().payee_entry.add_controller(focus_controller);

        self.imp().payee_popover.set(popover).ok();
        self.imp().payee_suggestion_list.set(suggestion_list).ok();
    }

    fn setup_signals(&self) {
        // Add button
        self.imp().add_button.connect_clicked(glib::clone!(
            #[weak(rename_to = window)]
            self,
            move |_| { window.on_add_expense(); }
        ));

        // Search
        self.imp().search_entry.connect_search_changed(glib::clone!(
            #[weak(rename_to = window)]
            self,
            move |_| {
                *window.imp().current_offset.borrow_mut() = 0;
                window.refresh_expenses();
            }
        ));

        // Payee autocomplete
        self.imp().payee_entry.connect_changed(glib::clone!(
            #[weak(rename_to = window)]
            self,
            move |_| { window.update_payee_suggestions(); }
        ));
    }

    fn on_add_expense(&self) {
        let amount_text = self.imp().amount_entry.text().replace(',', ".");
        let amount: f64 = match amount_text.parse() {
            Ok(v) if v > 0.0 => v,
            _ => return,
        };

        let payee = self.imp().payee_entry.text().trim().to_string();
        let note = self.imp().note_entry.text().trim().to_string();
        let is_income = self.imp().income_switch.is_active();
        let date = chrono::Local::now().format("%Y-%m-%d %H:%M").to_string();
        let account_id = *self.imp().current_account_id.borrow();

        self.db().add_expense(
            account_id, amount, &payee, &note, &date,
            is_income, false, None,
        ).ok();

        // Clear form
        self.imp().amount_entry.set_text("");
        self.imp().payee_entry.set_text("");
        self.imp().note_entry.set_text("");
        self.imp().income_switch.set_active(false);

        *self.imp().current_offset.borrow_mut() = 0;
        self.refresh_expenses();
    }

    pub(crate) fn refresh_expenses(&self) {
        let imp = self.imp();
        let account_id = *imp.current_account_id.borrow();
        if account_id == 0 { return; }

        let search_text = imp.search_entry.text();
        let search = if search_text.is_empty() { None } else { Some(search_text.as_str()) };

        // Update balance
        let balance = self.db().get_balance(account_id).unwrap_or(0.0);
        let balance_str = format!("{:.2} €", balance);
        imp.total_label.set_label(&balance_str);
        if balance >= 0.0 {
            imp.total_label.remove_css_class("error");
            imp.total_label.add_css_class("accent");
        } else {
            imp.total_label.remove_css_class("accent");
            imp.total_label.add_css_class("error");
        }

        // Update payees cache
        *imp.all_payees.borrow_mut() = self.db().get_all_payees(account_id).unwrap_or_default();

        // Load expenses
        let page_size: i64 = 50;
        let expenses = self.db().get_expenses(account_id, search, page_size, 0).unwrap_or_default();
        let total_count = self.db().get_expense_count(account_id, search).unwrap_or(0);

        // Clear list
        while let Some(child) = imp.expense_list.first_child() {
            imp.expense_list.remove(&child);
        }

        for expense in &expenses {
            let row = self.create_expense_row(expense);
            imp.expense_list.append(&row);
        }

        // "Show more" button if needed
        let shown = expenses.len() as i64;
        if shown < total_count {
            let remaining = total_count - shown;
            let more_btn = gtk::Button::builder()
                .label(format!("Show more ({} remaining)", remaining))
                .css_classes(vec!["flat"])
                .build();
            let row = adw::ActionRow::builder()
                .activatable(true)
                .child(&more_btn)
                .build();
            more_btn.connect_clicked(glib::clone!(
                #[weak(rename_to = window)]
                self,
                move |_| {
                    window.load_more_expenses(shown);
                }
            ));
            imp.expense_list.append(&row);
        }

        *imp.current_offset.borrow_mut() = shown;
    }

    fn load_more_expenses(&self, offset: i64) {
        let imp = self.imp();
        let account_id = *imp.current_account_id.borrow();

        let search_text = imp.search_entry.text();
        let search = if search_text.is_empty() { None } else { Some(search_text.as_str()) };

        let page_size: i64 = 50;
        let expenses = self.db().get_expenses(account_id, search, page_size, offset).unwrap_or_default();
        let total_count = self.db().get_expense_count(account_id, search).unwrap_or(0);

        // Remove the "show more" row (last child)
        if let Some(last) = imp.expense_list.last_child() {
            imp.expense_list.remove(&last);
        }

        for expense in &expenses {
            let row = self.create_expense_row(expense);
            imp.expense_list.append(&row);
        }

        let new_offset = offset + expenses.len() as i64;
        if new_offset < total_count {
            let remaining = total_count - new_offset;
            let more_btn = gtk::Button::builder()
                .label(format!("Show more ({} remaining)", remaining))
                .css_classes(vec!["flat"])
                .build();
            let row = adw::ActionRow::builder()
                .activatable(true)
                .child(&more_btn)
                .build();
            more_btn.connect_clicked(glib::clone!(
                #[weak(rename_to = window)]
                self,
                move |_| {
                    window.load_more_expenses(new_offset);
                }
            ));
            imp.expense_list.append(&row);
        }

        *imp.current_offset.borrow_mut() = new_offset;
    }

    fn create_expense_row(&self, expense: &crate::db::Expense) -> adw::ActionRow {
        let amount_str = if expense.is_income {
            format!("+{:.2} €", expense.amount)
        } else {
            format!("-{:.2} €", expense.amount)
        };

        let amount_label = gtk::Label::builder()
            .label(&amount_str)
            .build();
        if expense.is_income {
            amount_label.add_css_class("success");
        } else {
            amount_label.add_css_class("error");
        }

        let subtitle = if expense.note.is_empty() {
            expense.date.clone()
        } else {
            format!("{} • {}", expense.note, expense.date)
        };

        let title = if expense.payee.is_empty() {
            "(no payee)".to_string()
        } else {
            glib::markup_escape_text(&expense.payee).to_string()
        };

        let row = adw::ActionRow::builder()
            .title(&title)
            .subtitle(&subtitle)
            .activatable(true)
            .build();
        row.add_suffix(&amount_label);

        // Click row to edit
        let expense_clone = expense.clone();
        row.connect_activated(glib::clone!(
            #[weak(rename_to = window)]
            self,
            move |_| { window.show_edit_expense_dialog(&expense_clone); }
        ));

        // Action buttons box
        let btn_box = gtk::Box::builder()
            .orientation(gtk::Orientation::Horizontal)
            .spacing(4)
            .valign(gtk::Align::Center)
            .build();

        let expense_id = expense.id;
        let recurring_id = expense.recurring_id.clone();

        if let Some(ref rec_id) = recurring_id {
            // Edit recurring
            let edit_btn = gtk::Button::builder()
                .icon_name("document-edit-symbolic")
                .tooltip_text("Edit recurring")
                .css_classes(vec!["flat", "circular"])
                .valign(gtk::Align::Center)
                .build();
            let rec_id_clone = rec_id.clone();
            edit_btn.connect_clicked(glib::clone!(
                #[weak(rename_to = window)]
                self,
                move |_| { window.show_edit_recurring_dialog(&rec_id_clone); }
            ));
            btn_box.append(&edit_btn);

            // Stop recurring
            let stop_btn = gtk::Button::builder()
                .icon_name("process-stop-symbolic")
                .tooltip_text("Stop recurring")
                .css_classes(vec!["flat", "circular"])
                .valign(gtk::Align::Center)
                .build();
            let rec_id_clone = rec_id.clone();
            stop_btn.connect_clicked(glib::clone!(
                #[weak(rename_to = window)]
                self,
                move |_| { window.on_stop_recurring(&rec_id_clone); }
            ));
            btn_box.append(&stop_btn);
        } else {
            // Make recurring
            let rec_btn = gtk::Button::builder()
                .icon_name("view-refresh-symbolic")
                .tooltip_text("Make recurring")
                .css_classes(vec!["flat", "circular"])
                .valign(gtk::Align::Center)
                .build();
            rec_btn.connect_clicked(glib::clone!(
                #[weak(rename_to = window)]
                self,
                move |_| { window.show_make_recurring_dialog(expense_id); }
            ));
            btn_box.append(&rec_btn);
        }

        // Delete button
        let del_btn = gtk::Button::builder()
            .icon_name("user-trash-symbolic")
            .tooltip_text("Delete")
            .css_classes(vec!["flat", "circular"])
            .valign(gtk::Align::Center)
            .build();
        del_btn.connect_clicked(glib::clone!(
            #[weak(rename_to = window)]
            self,
            move |_| {
                window.db().delete_expense(expense_id).ok();
                window.refresh_expenses();
            }
        ));
        btn_box.append(&del_btn);

        row.add_suffix(&btn_box);
        row
    }

    fn show_edit_expense_dialog(&self, expense: &crate::db::Expense) {
        let dialog = adw::AlertDialog::builder()
            .heading("Edit Expense")
            .build();
        dialog.add_response("cancel", "Cancel");
        dialog.add_response("save", "Save");
        dialog.set_response_appearance("save", adw::ResponseAppearance::Suggested);

        let vbox = gtk::Box::builder()
            .orientation(gtk::Orientation::Vertical)
            .spacing(8)
            .build();

        let group = adw::PreferencesGroup::new();

        let payee_row = adw::EntryRow::builder()
            .title("Payee")
            .text(&expense.payee)
            .build();
        group.add(&payee_row);

        let amount_row = adw::EntryRow::builder()
            .title("Amount")
            .text(&format!("{:.2}", expense.amount))
            .input_purpose(gtk::InputPurpose::Number)
            .build();
        group.add(&amount_row);

        let note_row = adw::EntryRow::builder()
            .title("Note")
            .text(&expense.note)
            .build();
        group.add(&note_row);

        // Date: split into date and time
        let date_part = if expense.date.len() >= 10 { &expense.date[..10] } else { &expense.date };
        let time_part = if expense.date.len() >= 16 { &expense.date[11..16] } else { "12:00" };

        let date_row = adw::EntryRow::builder()
            .title("Date (YYYY-MM-DD)")
            .text(date_part)
            .build();
        group.add(&date_row);

        let time_row = adw::EntryRow::builder()
            .title("Time (HH:MM)")
            .text(time_part)
            .build();
        group.add(&time_row);

        let income_row = adw::SwitchRow::builder()
            .title("Income")
            .active(expense.is_income)
            .build();
        group.add(&income_row);

        vbox.append(&group);
        dialog.set_extra_child(Some(&vbox));

        let expense_id = expense.id;
        let recurring_id = expense.recurring_id.clone();

        dialog.choose(self, None::<&gio::Cancellable>, glib::clone!(
            #[weak(rename_to = window)]
            self,
            move |response| {
                if response != "save" {
                    return;
                }

                let amount_text = amount_row.text().replace(',', ".");
                let amount: f64 = match amount_text.parse() {
                    Ok(v) if v > 0.0 => v,
                    _ => return,
                };

                let payee = payee_row.text().trim().to_string();
                let note = note_row.text().trim().to_string();
                let date = date_row.text().trim().to_string();
                let time = time_row.text().trim().to_string();
                let is_income = income_row.is_active();

                // Validate date format
                if date.len() != 10 || date.chars().nth(4) != Some('-') {
                    return;
                }

                let full_date = if time.is_empty() {
                    format!("{} 12:00", date)
                } else {
                    format!("{} {}", date, time)
                };

                // Update the expense
                window.db().update_expense(expense_id, amount, &payee, &note, &full_date, is_income).ok();

                // If recurring, update the template so future instances use new values
                if let Some(ref rec_id) = recurring_id {
                    window.db().update_recurring_details(rec_id, amount, &payee, &note, is_income).ok();
                }

                window.refresh_expenses();
            }
        ));
    }

    fn update_payee_suggestions(&self) {
        let Some(popover) = self.imp().payee_popover.get() else { return };
        let Some(list) = self.imp().payee_suggestion_list.get() else { return };

        let text = self.imp().payee_entry.text().trim().to_string();

        // Clear existing suggestions
        while let Some(child) = list.first_child() {
            list.remove(&child);
        }

        if text.is_empty() {
            popover.popdown();
            return;
        }

        let text_lower = text.to_lowercase();
        let payees = self.imp().all_payees.borrow();
        let matches: Vec<&String> = payees.iter()
            .filter(|p| p.to_lowercase().contains(&text_lower))
            .collect();

        if matches.is_empty() {
            popover.popdown();
            return;
        }

        for payee in &matches {
            let label = gtk::Label::builder()
                .label(payee.as_str())
                .xalign(0.0)
                .margin_start(12)
                .margin_end(12)
                .margin_top(8)
                .margin_bottom(8)
                .build();
            let row = gtk::ListBoxRow::builder()
                .child(&label)
                .build();
            list.append(&row);
        }

        popover.popup();
    }

    // --- Recurring Expenses ---

    fn process_recurring_expenses(&self) {
        let recurring = self.db().get_recurring_expenses().unwrap_or_default();
        let today = chrono::Local::now().format("%Y-%m-%d").to_string();

        for rec in &recurring {
            let mut next_date = rec.last_generated.clone();
            let mut last_actually_generated: Option<String> = None;

            loop {
                next_date = Self::add_frequency(&next_date, &rec.frequency);
                let next_date_str = &next_date[..10]; // "YYYY-MM-DD"

                if next_date_str > today.as_str() { break; }

                if let Some(ref end) = rec.end_date {
                    if next_date_str > end.as_str() { break; }
                }

                if !self.db().expense_exists_on_date(rec.account_id, &rec.id, next_date_str)
                    .unwrap_or(true)
                {
                    let datetime = format!("{} 00:00", next_date_str);
                    self.db().add_expense(
                        rec.account_id, rec.amount, &rec.payee, &rec.note,
                        &datetime, rec.is_income, false, Some(&rec.id),
                    ).ok();
                }

                // Track the last scheduled date we processed (whether or not
                // the expense already existed) so that last_generated advances
                // along the schedule instead of drifting to today.
                last_actually_generated = Some(next_date_str.to_string());
            }

            // Only advance last_generated to the last scheduled date we
            // reached, NOT to today.  This prevents the schedule from
            // drifting when the app is opened daily.
            if let Some(ref gen_date) = last_actually_generated {
                self.db().update_recurring_last_generated(&rec.id, gen_date).ok();
            }
        }
    }

    fn add_frequency(date_str: &str, frequency: &str) -> String {
        let date = chrono::NaiveDate::parse_from_str(&date_str[..10], "%Y-%m-%d")
            .unwrap_or_else(|_| chrono::Local::now().date_naive());

        // Handle "Xm" format (every X months)
        if let Some(n_str) = frequency.strip_suffix('m') {
            if let Ok(n) = n_str.parse::<u32>() {
                let total = date.month0() + n;
                let new_year = date.year() + (total / 12) as i32;
                let new_month = total % 12 + 1;
                let max_day = days_in_month(new_year, new_month);
                let day = date.day().min(max_day);
                return chrono::NaiveDate::from_ymd_opt(new_year, new_month, day)
                    .unwrap_or(date)
                    .format("%Y-%m-%d")
                    .to_string();
            }
        }

        let new_date = match frequency {
            "daily" => date + chrono::Duration::days(1),
            "weekly" => date + chrono::Duration::days(7),
            "monthly" => {
                let month = date.month();
                let year = date.year();
                let (new_year, new_month) = if month == 12 {
                    (year + 1, 1)
                } else {
                    (year, month + 1)
                };
                let max_day = days_in_month(new_year, new_month);
                let day = date.day().min(max_day);
                chrono::NaiveDate::from_ymd_opt(new_year, new_month, day)
                    .unwrap_or(date)
            }
            "yearly" => {
                let new_year = date.year() + 1;
                let max_day = days_in_month(new_year, date.month());
                let day = date.day().min(max_day);
                chrono::NaiveDate::from_ymd_opt(new_year, date.month(), day)
                    .unwrap_or(date)
            }
            _ => date + chrono::Duration::days(1),
        };
        new_date.format("%Y-%m-%d").to_string()
    }

    fn show_make_recurring_dialog(&self, expense_id: i64) {
        let dialog = adw::AlertDialog::builder()
            .heading("Make Recurring")
            .body("Choose how often this expense should repeat:")
            .build();
        dialog.add_response("cancel", "Cancel");
        dialog.add_response("create", "Create");
        dialog.set_response_appearance("create", adw::ResponseAppearance::Suggested);

        let vbox = gtk::Box::builder()
            .orientation(gtk::Orientation::Vertical)
            .spacing(12)
            .build();

        let freq_list = gtk::StringList::new(&["Daily", "Weekly", "Monthly", "Yearly", "Every N months"]);
        let freq_dropdown = gtk::DropDown::builder()
            .model(&freq_list)
            .selected(2) // Monthly default
            .build();
        vbox.append(&freq_dropdown);

        let months_adj = gtk::Adjustment::new(3.0, 2.0, 120.0, 1.0, 1.0, 0.0);
        let months_spin = gtk::SpinButton::new(Some(&months_adj), 1.0, 0);
        months_spin.set_sensitive(false);
        months_spin.set_tooltip_text(Some("Number of months between occurrences"));
        vbox.append(&months_spin);

        freq_dropdown.connect_notify_local(Some("selected"), glib::clone!(
            #[weak]
            months_spin,
            move |dropdown, _| {
                months_spin.set_sensitive(dropdown.selected() == 4);
            }
        ));

        let end_row = adw::EntryRow::builder()
            .title("End date (optional, YYYY-MM-DD)")
            .build();
        vbox.append(&end_row);

        dialog.set_extra_child(Some(&vbox));

        dialog.choose(self, None::<&gio::Cancellable>, glib::clone!(
            #[weak(rename_to = window)]
            self,
            move |response| {
                if response == "create" {
                    let freq = if freq_dropdown.selected() == 4 {
                        format!("{}m", months_spin.value() as u32)
                    } else {
                        match freq_dropdown.selected() {
                            0 => "daily".to_string(),
                            1 => "weekly".to_string(),
                            2 => "monthly".to_string(),
                            3 => "yearly".to_string(),
                            _ => "monthly".to_string(),
                        }
                    };
                    let end_text = end_row.text().trim().to_string();
                    let end_date = if end_text.is_empty() { None } else { Some(end_text) };

                    window.make_expense_recurring(expense_id, &freq, end_date.as_deref());
                }
            }
        ));
    }

    fn make_expense_recurring(&self, expense_id: i64, frequency: &str, end_date: Option<&str>) {
        // Get the expense details from the list
        let account_id = *self.imp().current_account_id.borrow();
        let expenses = self.db().get_expenses(account_id, None, 10000, 0).unwrap_or_default();
        let expense = expenses.iter().find(|e| e.id == expense_id);

        if let Some(expense) = expense {
            let rec_id = uuid::Uuid::new_v4().to_string();
            // Use the expense's own date as start_date and last_generated
            // so the recurring schedule is anchored to the original expense,
            // not to when the user happened to press "make recurring".
            let expense_date = &expense.date[..10]; // "YYYY-MM-DD"

            self.db().add_recurring_expense(
                &rec_id, expense.account_id, expense.amount, &expense.payee,
                &expense.note, expense.is_income, frequency, expense_date,
                end_date, expense_date,
            ).ok();

            // Update the original expense to link it
            self.db().connection().execute(
                "UPDATE expenses SET recurring_id = ?1 WHERE id = ?2",
                rusqlite::params![rec_id, expense_id],
            ).ok();

            self.refresh_expenses();
        }
    }

    fn show_edit_recurring_dialog(&self, recurring_id: &str) {
        let rec = match self.db().get_recurring_expense(recurring_id) {
            Ok(Some(r)) => r,
            _ => return,
        };

        let dialog = adw::AlertDialog::builder()
            .heading("Edit Recurring")
            .body("Change the frequency or end date:")
            .build();
        dialog.add_response("cancel", "Cancel");
        dialog.add_response("save", "Save");
        dialog.set_response_appearance("save", adw::ResponseAppearance::Suggested);

        let vbox = gtk::Box::builder()
            .orientation(gtk::Orientation::Vertical)
            .spacing(12)
            .build();

        let (selected_idx, months_value) = if let Some(n_str) = rec.frequency.strip_suffix('m') {
            (4u32, n_str.parse::<f64>().unwrap_or(3.0))
        } else {
            let idx = match rec.frequency.as_str() {
                "daily" => 0,
                "weekly" => 1,
                "monthly" => 2,
                "yearly" => 3,
                _ => 2,
            };
            (idx, 3.0)
        };

        let freq_list = gtk::StringList::new(&["Daily", "Weekly", "Monthly", "Yearly", "Every N months"]);
        let freq_dropdown = gtk::DropDown::builder()
            .model(&freq_list)
            .selected(selected_idx)
            .build();
        vbox.append(&freq_dropdown);

        let months_adj = gtk::Adjustment::new(months_value, 2.0, 120.0, 1.0, 1.0, 0.0);
        let months_spin = gtk::SpinButton::new(Some(&months_adj), 1.0, 0);
        months_spin.set_sensitive(selected_idx == 4);
        months_spin.set_tooltip_text(Some("Number of months between occurrences"));
        vbox.append(&months_spin);

        freq_dropdown.connect_notify_local(Some("selected"), glib::clone!(
            #[weak]
            months_spin,
            move |dropdown, _| {
                months_spin.set_sensitive(dropdown.selected() == 4);
            }
        ));

        let end_row = adw::EntryRow::builder()
            .title("End date (optional, YYYY-MM-DD)")
            .text(rec.end_date.as_deref().unwrap_or(""))
            .build();
        vbox.append(&end_row);

        dialog.set_extra_child(Some(&vbox));

        let rec_id = recurring_id.to_string();
        dialog.choose(self, None::<&gio::Cancellable>, glib::clone!(
            #[weak(rename_to = window)]
            self,
            move |response| {
                if response == "save" {
                    let freq = if freq_dropdown.selected() == 4 {
                        format!("{}m", months_spin.value() as u32)
                    } else {
                        match freq_dropdown.selected() {
                            0 => "daily".to_string(),
                            1 => "weekly".to_string(),
                            2 => "monthly".to_string(),
                            3 => "yearly".to_string(),
                            _ => "monthly".to_string(),
                        }
                    };
                    let end_text = end_row.text().trim().to_string();
                    let end_date = if end_text.is_empty() { None } else { Some(end_text.as_str()) };

                    window.db().update_recurring_frequency(&rec_id, &freq, end_date).ok();
                    window.refresh_expenses();
                }
            }
        ));
    }

    fn on_stop_recurring(&self, recurring_id: &str) {
        let dialog = adw::AlertDialog::builder()
            .heading("Stop Recurring?")
            .body("This will stop future automatic entries. Existing expenses will be kept.")
            .build();
        dialog.add_response("cancel", "Cancel");
        dialog.add_response("stop", "Stop");
        dialog.set_response_appearance("stop", adw::ResponseAppearance::Destructive);

        let rec_id = recurring_id.to_string();
        dialog.choose(self, None::<&gio::Cancellable>, glib::clone!(
            #[weak(rename_to = window)]
            self,
            move |response| {
                if response == "stop" {
                    window.db().delete_recurring_expense(&rec_id).ok();
                    window.refresh_expenses();
                }
            }
        ));
    }

    // Import/export implemented in import_export.rs
}

fn days_in_month(year: i32, month: u32) -> u32 {
    match month {
        1 | 3 | 5 | 7 | 8 | 10 | 12 => 31,
        4 | 6 | 9 | 11 => 30,
        2 => {
            if (year % 4 == 0 && year % 100 != 0) || year % 400 == 0 {
                29
            } else {
                28
            }
        }
        _ => 30,
    }
}

use chrono::Datelike;
