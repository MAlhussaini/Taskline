# Taskline

A responsive personal planning app built with Python's standard library. It includes dated checklists, an Inbox with persistent planning choices, colored labels, top-three priorities, parent/child tasks, Dreams with optional images and inner steps, and a period-based History view. Data is stored locally in SQLite and the interface works across desktop, phone, and tablet.

## Run it

1. Install Python 3.10 or newer from https://www.python.org/downloads/
2. Open a terminal in this folder.
3. Run `python app.py`.
4. Open http://localhost:8000 on your PC.

To use it from a phone or tablet on the same Wi-Fi network, open `http://YOUR-PC-IP:8000` on that device. Windows may ask you to allow Python through the firewall the first time.

Tasks are saved in `tasks.db`, which is created automatically beside `app.py`.
