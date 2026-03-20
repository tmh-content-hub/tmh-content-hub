# TMH Content Hub

A password-protected customer portal for Travel Marketing Hub (TMH).
Service 2 subscribers log in and access their destination content packs —
download links for blogs, social posts, promo assets, and Canva templates.

---

## Default Login Credentials

| Role     | Username / Email        | Password          |
|----------|-------------------------|-------------------|
| Admin    | `admin`                 | `tmh-admin-2024`  |
| Customer | `sarah@example.com`     | `welcome123`      |

**Change all passwords immediately after first login via the Admin Panel.**

---

## Running Locally

### 1. Install Python dependencies

Make sure you have Python 3.9+ installed. Then, from inside the `tmh-content-hub` folder:

```bash
pip install -r requirements.txt
```

### 2. Start the app

```bash
python app.py
```

Then open your browser and go to: **http://localhost:5000**

- Customer login: http://localhost:5000/login
- Admin panel: http://localhost:5000/admin

---

## Deploying to Render (free tier)

Render is a hosting service that can run this app for free. Here's how:

### Step 1 — Create an account
Go to [render.com](https://render.com) and sign up for a free account.

### Step 2 — Push to GitHub
1. Create a new GitHub repository (e.g. `tmh-content-hub`)
2. Upload all the files from this folder to that repository
3. You can use the GitHub website to drag and drop the files, or use GitHub Desktop

### Step 3 — Create a Web Service on Render
1. In Render, click **New → Web Service**
2. Connect your GitHub account and select the `tmh-content-hub` repository
3. Fill in these settings:
   - **Name:** tmh-content-hub (or anything you like)
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`
4. Under **Environment Variables**, add:
   - Key: `SECRET_KEY`  Value: any long random string (e.g. `my-super-secret-key-abc123xyz`)
5. Click **Create Web Service**

Render will build and deploy automatically. Your portal will be live at a URL like `https://tmh-content-hub.onrender.com`.

> **Note:** On Render's free tier, the app "sleeps" after 15 minutes of inactivity and takes ~30 seconds to wake up on the next visit. Upgrade to a paid plan to avoid this.

---

## Deploying to Railway

Railway is another easy hosting option.

### Step 1 — Install Railway CLI (optional)
Or use the Railway website at [railway.app](https://railway.app).

### Step 2 — Deploy via website
1. Go to railway.app and sign up
2. Click **New Project → Deploy from GitHub repo**
3. Select your `tmh-content-hub` repository
4. Railway auto-detects Python — set the start command to: `gunicorn app:app`
5. In **Variables**, add `SECRET_KEY` with a random value
6. Railway will give you a public URL automatically

---

## Managing Customers & Destinations

Everything is managed through the **Admin Panel** at `/admin`.

### Adding a new customer
1. Log in to `/admin` with your admin credentials
2. Go to the **Customers** tab
3. Fill in their name, email, and an initial password → click **Add Customer**
4. Share their email and password with them directly

### Adding a new destination
1. Go to the **Destinations** tab
2. Enter the destination name, flag emoji, and set status to **Ready** or **Coming Soon**
3. Click **Add Destination**

### Assigning destinations and adding links
1. Go to the **Assign & Links** tab
2. Select the customer from the dropdown
3. Tick the checkbox next to each destination they should have access to
4. Paste in the Google Drive and Canva URLs for each destination
5. Click **Save Links** for each destination

### Resetting a customer password
1. In the **Customers** tab, click **Reset password** next to their name
2. Enter a new password and confirm

---

## File Structure

```
tmh-content-hub/
├── app.py              ← Main Flask application
├── data.json           ← All customer & destination data (edit via admin panel)
├── requirements.txt    ← Python dependencies
├── README.md           ← This file
├── templates/
│   ├── login.html      ← Customer login page
│   ├── admin_login.html← Admin login page
│   ├── dashboard.html  ← Customer dashboard
│   └── admin.html      ← Admin panel
└── static/
    ├── style.css       ← All styles
    ├── app.js          ← Frontend JavaScript
    └── img/
        └── logo.png    ← TMH logo (replace with your logo file)
```

---

## Adding the TMH Logo

Place your logo file at `static/img/logo.png`. The app will display it automatically in the header. If no logo is found, the text "Travel Marketing Hub" is shown instead.

---

## Security Notes

- Passwords are stored as bcrypt hashes — never in plain text
- Sessions use a server-side secret key — always set `SECRET_KEY` as an environment variable in production
- The admin panel is behind a separate login with a separate role check
- All customer routes require an active login session
