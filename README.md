# Imortant
I wanted to switch this app to Rust since i dont know what im doing anyway so might as well take the potential performance improvements. Since this was already kinda pmo because I made the wrong decisions in some or a lot of cases I decided to go with a new repo for this app. https://github.com/nico359/expenses

# Expenses

A vibe coded attempt at creating a mobile friendly expenses tracker for Linux. More or less just to see what different AI chatbots are capable of. So far I mostly used the free plan of Copilot with the Claude Haiku 4.5 model. For the major changes in version 2.0 (switch to sqlite) I used Claude Opus 4.6 now.

It is somewhat inspired by the Android App MyExpenses from Michael Totschnig. Therefore it has the ability to import the BACKUP Database MyExpenses creates. It should also be able to just take the zip file created by the Android App now.

https://github.com/mtotschnig/MyExpenses

# Building

The easiest way to build the app from source is by using the Gnome Builder IDE.

# Note

A note about the commit history:
The two commits from 18.03.2026 are not actually from this day (right now it says "commited next week"). I tested something with recurring expenses and therefore manipulated the system time. Unfortunately i forgot to set the date correctly before commiting. These two commits were made on 11.03.2026.
