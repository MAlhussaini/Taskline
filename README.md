# Taskline

A responsive personal planning app built with Python's standard library. It includes dated checklists, an Inbox with persistent planning choices, colored labels, top-three priorities, parent/child tasks, Dreams with optional images and inner steps, and a period-based History view. Data is stored locally in SQLite and the interface works across desktop, phone, and tablet.

## Run it

1. Install Python 3.10 or newer from https://www.python.org/downloads/
2. Open a terminal in this folder.
3. Run `python app.py`.
4. Open http://localhost:8000 on your PC.

To use it from a phone or tablet on the same Wi-Fi network, open `http://YOUR-PC-IP:8000` on that device. Windows may ask you to allow Python through the firewall the first time.

Tasks are saved in `tasks.db`, which is created automatically beside `app.py`.

## Install on a phone

Taskline includes a web app manifest, mobile icons, standalone display support, and an offline app shell. It must be opened over HTTPS before a browser can install it.

On this Taskline PC, connect the phone to the same Tailscale network and open `https://taskline.tail3c6613.ts.net/`. Use the install button in Taskline or the browser's **Install app / Add to Home Screen** command. On iPhone or iPad, open the Share menu and choose **Add to Home Screen**.

Taskline uses the separate `tailscaled-taskline.service` userspace identity included in `deploy/`. This gives the PWA its own hostname and prevents an installed app on the main `debian` hostname, such as Codex, from capturing Taskline links. The system service and its Serve configuration persist across restarts.

The interface shell can open offline after the first successful visit. Creating or changing tasks still requires a connection to the Taskline PC because all personal data stays in its local SQLite database.
