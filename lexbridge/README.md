# LexBridge — How to Run

LexBridge is a Flask + MySQL platform that connects **vehicle owners (clients)** with **lawyers**.
Clients open cases and send requests to lawyers; lawyers browse open cases, express interest,
and accept/reject incoming requests. This document is just the run instructions.

---

## 1. Prerequisites

Install these once:

- **Python 3.11+**
- **MySQL 8.0+** running locally on port `3306`
- **pip** and **venv** (ship with Python)
- A modern browser

Optional: a Gmail **App Password** if you want real email delivery for
verification / password-reset links.

---

## 2. First-time setup

### 2.1 Open the project folder

```bash
cd path\to\lexbridge
```

### 2.2 Create and activate a virtual environment

**Windows (PowerShell / CMD)**

```bash
python -m venv myenv
myenv\Scripts\activate
```

**macOS / Linux**

```bash
python3 -m venv myenv
source myenv/bin/activate
```

You should see `(myenv)` at the start of your shell prompt.

### 2.3 Install the Python dependencies

```bash
pip install -r requirements.txt
```

### 2.4 Create the MySQL database

In a MySQL shell:

```sql
CREATE DATABASE lexbridge CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

You do **not** need to load `schema.sql` manually — `db.create_all()` builds
every table (including the new `case_requests` table) on the first boot.

### 2.5 Create your `.env` file

```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

Edit `.env` and set at minimum:

```env
FLASK_ENV=development
SECRET_KEY=<run: python -c "import secrets; print(secrets.token_hex(32))">
JWT_SECRET_KEY=<run the same command again for a different value>
DATABASE_URL=mysql+mysqlconnector://root:YOUR_MYSQL_PASSWORD@localhost:3306/lexbridge
```

Leave the `MAIL_*` and `CORS_ORIGINS` lines as-is for local development.

---

## 3. Run the server

With the venv still active:

```bash
python app.py
```

Flask starts on **http://localhost:5000** and auto-creates every table on the
first run.

In a **second terminal**, serve the HTML frontend:

```bash
python -m http.server 8080
```

Then visit **http://localhost:8080** in your browser.

Pages you will use:

- `index.html` — landing page
- `signup.html` / `login.html` — auth
- `client_dashboard.html` — client portal
- `lawyer_dashboard.html` — lawyer portal
- `admin_panel.html` — admin control panel

The frontend uses `scripts/api.js` to talk to the Flask API at
`http://localhost:5000`. If the server is unreachable it falls back to
localStorage so the UI keeps working offline.

---

## 4. Create an admin account

The first admin has to be created from the CLI:

```bash
python manage.py create_admin --email admin@lexbridge.in --name "Platform Admin"
```

You will be prompted for a password (min 8 characters). After that, log in
through `login.html` and open `admin_panel.html`.

Other handy commands:

```bash
python manage.py list_users    # show the 50 newest users
python manage.py reset_db      # DROP + recreate every table (dev only)
```

---

## 5. Typical usage flow

**Client**

1. Register from `signup.html` as role `client`.
2. Log in — you land on `client_dashboard.html`.
3. Open a new case from **My Cases**.
4. Go to **Find Lawyers**, pick one, click **Send Case Request**, attach one of
   your open cases, and submit.
5. The **Requests** tab shows the status (pending / accepted / rejected). When a
   lawyer expresses interest in one of your cases, you accept or deny it here.

**Lawyer**

1. Register as role `lawyer` and wait for an admin to mark your profile
   verified.
2. Log in — you land on `lawyer_dashboard.html`.
3. Browse **Open Cases** and click **Express Interest** on anything relevant.
4. Check the **Requests** tab for incoming client requests. Accepting one
   auto-assigns the case to you and auto-rejects every other pending request
   for that same case.

All reads and writes go through `/api/*` endpoints — no direct browser-to-DB
access.

---

## 6. Production run

Use Gunicorn instead of `python app.py`:

```bash
gunicorn -w 4 -b 0.0.0.0:5000 "app:create_app()"
```

Required in production `.env`:

- `FLASK_ENV=production`
- `SECRET_KEY` and `JWT_SECRET_KEY` — strong random values
- `DATABASE_URL` — your real MySQL URL
- `CORS_ORIGINS` — exact frontend URL(s), comma-separated (no `*`)
- `MAIL_*` — SMTP credentials if you want real email
- `BASE_URL` — public URL used in email links

The app refuses to start in production if any of `SECRET_KEY`, `JWT_SECRET_KEY`,
or `CORS_ORIGINS` are missing.

---

## 7. Troubleshooting

**"Import could not be resolved" in VSCode**
Open the project from its root folder (the one containing `app.py`). The
included `pyrightconfig.json` and `.vscode/settings.json` add `.` to Pylance's
import roots. Restart the Python language server after opening.

**`RuntimeError: DATABASE_URL environment variable is not set`**
You haven't created `.env` or it doesn't contain `DATABASE_URL`. Re-do
step 2.5.

**`Access denied for user 'root'@'localhost'`**
The MySQL password in `DATABASE_URL` is wrong, or the `lexbridge` database
doesn't exist. Re-check step 2.4.

**Frontend shows "Network unavailable — running in offline mode"**
`python app.py` isn't running, or the frontend origin isn't listed in
`CORS_ORIGINS`. Start the server and (if needed) add `http://localhost:8080`
to `CORS_ORIGINS` in `.env`.

**Emails aren't sending**
Expected unless you set `MAIL_USERNAME` / `MAIL_PASSWORD` in `.env`. Use a
[Gmail App Password](https://support.google.com/accounts/answer/185833), not
your normal account password.
