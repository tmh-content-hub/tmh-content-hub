import os
import json
import hashlib
import secrets
import psycopg2
import psycopg2.extras
import urllib.request as urllib_req
from datetime import date, datetime, timedelta
from functools import wraps
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, jsonify
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "tmh-dev-secret-change-in-production")
app.config["PERMANENT_SESSION_LIFETIME"] = 60 * 60 * 24 * 30  # 30 days
DATABASE_URL = os.environ.get("DATABASE_URL", "")
DATA_FILE = os.path.join(os.path.dirname(__file__), "data.json")

MONTH_NAMES = ["January","February","March","April","May","June",
               "July","August","September","October","November","December"]

FILE_FIELDS = ["social_media", "blog", "canva_guides", "reels", "promo_assets"]

OFFER_LIMITS = {"core": 0, "pro": 4, "managed": 8}

# ── Supplier reel slot assignment ──────────────────────────────────────────────
SLOT_LABELS = {
    "Aerial":          "🛩 Aerial / Drone overview",
    "LateralFly":      "🌊 Lateral Fly — outdoor wide",
    "CraneUp_Reveal":  "🏛 Crane Up — exterior/landmark",
    "LateralInterior": "🛋 Interior — lobby/restaurant/spa",
    "DollyOut":        "🛏 Dolly — bedroom/suite/villa",
    "LockedZoom":      "🔭 Zoom — strongest focal point",
}

STYLE_NAMES = {1: "Cinematic", 2: "Bold", 3: "Bright", 4: "Soft"}

# Clip order per style
STYLE_SEQUENCES = {
    1: ["Aerial", "CraneUp_Reveal", "LateralFly", "DollyOut", "LateralInterior", "LockedZoom"],
    2: ["Aerial", "LockedZoom", "LateralFly", "LateralInterior", "CraneUp_Reveal", "DollyOut"],
    3: ["Aerial", "LateralFly", "DollyOut", "CraneUp_Reveal", "LockedZoom", "LateralInterior"],
    4: ["Aerial", "DollyOut", "LateralInterior", "LockedZoom", "LateralFly", "CraneUp_Reveal"],
}

# Freepik / Higgsfield camera movement prompts per style × slot
CAMERA_PROMPTS = {
    1: {  # Cinematic
        "Aerial":          "Cinematic aerial drone shot pushing forward over resort, smooth confident forward momentum from above, establishing wide view, premium travel atmosphere, natural daylight, modern commercial energy",
        "CraneUp_Reveal":  "Slow crane up. Camera movement only. Keep all buildings and background structures rigid and unchanged. Preserve exact geometry and perspective. No distortion, morphing, stretching, or added elements. Natural daylight.",
        "LateralFly":      "Dynamic lateral fly-by with pronounced depth shift and confident cinematic motion, modern commercial travel energy, clean lines, natural daylight",
        "DollyOut":        "Subtle dynamic lateral movement with confident pacing, natural lifestyle atmosphere, modern commercial travel energy",
        "LateralInterior": "Cinematic lateral slide movement with confident but controlled pace, subtle depth shift across interior space, modern travel aesthetic, clean natural daylight",
        "LockedZoom":      "Refined forward cinematic push with clean depth motion and confident energy, premium travel atmosphere, modern commercial style",
    },
    2: {  # Bold
        "Aerial":          "Dynamic aerial drone shot pushing forward, fast energetic momentum from above, high-impact establishing view, natural daylight, bold commercial travel energy",
        "LockedZoom":      "Strong fast forward push with sharp depth motion and bold energy, high-impact travel atmosphere, modern dynamic commercial style",
        "LateralFly":      "High-energy lateral fly-by with sharp depth shift and fast kinetic motion, bold commercial travel energy, clean lines, natural daylight",
        "LateralInterior": "Dynamic lateral slide with fast confident pace, pronounced depth shift across interior space, bold modern travel aesthetic, clean natural daylight",
        "CraneUp_Reveal":  "Fast confident crane up. Camera movement only. Keep all buildings and background structures rigid and unchanged. Preserve exact geometry and perspective. No distortion, morphing, stretching, or added elements. Natural daylight.",
        "DollyOut":        "Energetic lateral movement with fast confident pacing, bold lifestyle atmosphere, high-impact commercial travel energy",
    },
    3: {  # Bright
        "Aerial":          "Warm aerial drone shot gently pushing forward, easy light momentum from above, inviting establishing view, warm natural daylight, cheerful lifestyle travel energy",
        "LateralFly":      "Smooth light lateral fly-by with easy depth shift and bright cheerful motion, warm lifestyle travel energy, clean lines, natural daylight",
        "DollyOut":        "Easy gentle lateral movement with relaxed pacing, warm natural lifestyle atmosphere, bright cheerful travel energy",
        "CraneUp_Reveal":  "Warm gentle crane up. Camera movement only. Keep all buildings and background structures rigid and unchanged. Preserve exact geometry and perspective. No distortion, morphing, stretching, or added elements. Warm natural daylight.",
        "LockedZoom":      "Gentle warm forward push with light depth motion and inviting energy, bright travel atmosphere, cheerful lifestyle commercial style",
        "LateralInterior": "Light lateral slide with easy natural pace, soft depth shift across interior space, warm inviting travel aesthetic, bright natural daylight",
    },
    4: {  # Soft
        "Aerial":          "Slow dreamy aerial drone drift pushing gently forward, barely perceptible momentum from above, soft establishing view, ethereal travel atmosphere, soft natural daylight, romantic lifestyle energy",
        "DollyOut":        "Very slow gentle lateral drift with peaceful pacing, dreamy romantic atmosphere, soft intimate lifestyle travel energy",
        "LateralInterior": "Slow gentle lateral glide with soft intimate pace, barely perceptible depth shift across interior space, romantic dreamy travel aesthetic, soft natural daylight",
        "LockedZoom":      "Slow soft forward drift with gentle depth movement and dreamy energy, ethereal travel atmosphere, romantic intimate lifestyle style",
        "LateralFly":      "Slow dreamy lateral drift with soft depth shift and gentle floating motion, romantic lifestyle travel energy, clean lines, soft natural daylight",
        "CraneUp_Reveal":  "Very slow gentle crane up. Camera movement only. Keep all buildings and background structures rigid and unchanged. Preserve exact geometry and perspective. No distortion, morphing, stretching, or added elements. Soft natural daylight.",
    },
}

SUPABASE_URL         = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
ALLOWED_IMAGE_TYPES  = {"image/jpeg","image/png"}
HIGHLEVEL_WEBHOOK_URL            = os.environ.get("HIGHLEVEL_WEBHOOK_URL", "")
HIGHLEVEL_MAGIC_LINK_WEBHOOK_URL = os.environ.get("HIGHLEVEL_MAGIC_LINK_WEBHOOK_URL", "")
OPENAI_API_KEY                   = os.environ.get("Render_Claude_Video_Reels", "")

def upload_image(file_bytes, path, content_type):
    """Upload a file to Supabase Storage and return its public URL."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        return None
    try:
        url = f"{SUPABASE_URL}/storage/v1/object/offer-images/{path}"
        req = urllib_req.Request(url, data=file_bytes, method="POST")
        req.add_header("Authorization", f"Bearer {SUPABASE_SERVICE_KEY}")
        req.add_header("Content-Type", content_type or "image/jpeg")
        req.add_header("x-upsert", "true")
        urllib_req.urlopen(req)
        return f"{SUPABASE_URL}/storage/v1/object/public/offer-images/{path}"
    except Exception:
        return None

def fire_hl_webhook(customer_name, customer_email, plan, offer_url, caption, image_count, submitted_at):
    """POST offer submission details to HighLevel inbound webhook (silent fail)."""
    if not HIGHLEVEL_WEBHOOK_URL:
        return
    try:
        payload = json.dumps({
            "event":          "offer_submitted",
            "name":           customer_name,
            "email":          customer_email,
            "plan":           plan,
            "offer_url":      offer_url,
            "caption":        caption,
            "image_count":    image_count,
            "submitted_at":   submitted_at,
            "note": (
                f"New supplier offer submitted via TMH Content Hub.\n\n"
                f"Plan: {plan.capitalize()}\n"
                f"Offer URL: {offer_url}\n"
                f"Images uploaded: {image_count}\n"
                f"Post copy:\n{caption}\n\n"
                f"Submitted: {submitted_at}"
            ),
        }).encode("utf-8")
        req = urllib_req.Request(HIGHLEVEL_WEBHOOK_URL, data=payload, method="POST")
        req.add_header("Content-Type", "application/json")
        urllib_req.urlopen(req, timeout=5)
    except Exception:
        pass  # Never block a submission if HL is unreachable

# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def get_db():
    return psycopg2.connect(DATABASE_URL)

def row_to_dest(r):
    """Convert a DB row to the template-friendly destination dict."""
    d = dict(r)
    d['files'] = {f: d.pop(f, '') or '' for f in FILE_FIELDS}
    if d.get('assigned_dest_ids') is None:
        d['assigned_dest_ids'] = []
    return d

def check_password(plain, stored):
    if stored.startswith("$2b$") or stored.startswith("$2a$"):
        try:
            import bcrypt
            return bcrypt.checkpw(plain.encode("utf-8"), stored.encode("utf-8"))
        except Exception:
            return False
    return sha256(plain) == stored

def rolling_window():
    today = date.today()
    m, y = today.month, today.year
    prev_m = 12 if m == 1 else m - 1
    prev_y = y - 1 if m == 1 else y
    next_m = 1 if m == 12 else m + 1
    next_y = y + 1 if m == 12 else y
    return (prev_m, prev_y), (m, y), (next_m, next_y)

# ─────────────────────────────────────────────
# Auth decorators
# ─────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session or session.get("role") != "customer":
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get("admin_role") != "admin":
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated

def api_admin_required(f):
    """Like admin_required but returns JSON 401 instead of redirecting — for API/fetch routes."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get("admin_role") != "admin":
            return jsonify({"error": "Session expired — please refresh the admin page and log in again."}), 401
        return f(*args, **kwargs)
    return decorated

# ─────────────────────────────────────────────
# One-time setup / seed from data.json
# ─────────────────────────────────────────────

@app.route("/setup")
def setup():
    """Seed the database from data.json. Only works when DB is empty."""
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT COUNT(*) as n FROM admin_settings")
        if cur.fetchone()['n'] > 0:
            cur.close(); conn.close()
            return ("<h2>Already set up — nothing to do.</h2>"
                    "<p><a href='/'>Go to customer login</a> &nbsp;|&nbsp; "
                    "<a href='/admin'>Go to admin</a></p>")

        if not os.path.exists(DATA_FILE):
            cur.close(); conn.close()
            return "<h2>❌ No data.json found. Cannot seed.</h2>", 500

        with open(DATA_FILE) as f:
            data = json.load(f)

        admin = data.get("admin", {})
        cur.execute(
            "INSERT INTO admin_settings (key, value) VALUES (%s,%s),(%s,%s)",
            ("username", admin.get("username","admin"),
             "password_hash", admin.get("password_hash", sha256("tmh-admin-2024")))
        )

        for c in data.get("customers", []):
            cur.execute("""
                INSERT INTO customers
                    (id, name, email, password_hash, joined_date, notes, assigned_dest_ids)
                VALUES (%s,%s,%s,%s,%s,%s,'{}')
            """, (c["id"], c["name"], c["email"], c["password_hash"],
                  c.get("joined_date", date.today().isoformat()), c.get("notes","")))

        for d in data.get("destinations", []):
            f = d.get("files", {})
            cur.execute("""
                INSERT INTO destinations
                    (id, name, flag, month, year, status,
                     blog_docx, social_posts, promo_assets, guide_pdf,
                     images_folder, canva_guide, canva_carousel, canva_pinterest)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (d["id"], d["name"], d.get("flag","🌍"), d["month"], d["year"],
                  d.get("status","coming_soon"),
                  f.get("blog_docx",""), f.get("social_posts",""), f.get("promo_assets",""),
                  f.get("guide_pdf",""), f.get("images_folder",""), f.get("canva_guide",""),
                  f.get("canva_carousel",""), f.get("canva_pinterest","")))

        conn.commit()
        cur.close(); conn.close()
        return ("<h2>✅ Setup complete!</h2>"
                "<p>Database seeded with all customers and destinations.</p>"
                "<p><a href='/'>Customer login</a> &nbsp;|&nbsp; "
                "<a href='/admin'>Admin panel</a></p>")
    except Exception as e:
        return f"<h2>❌ Setup failed</h2><pre>{e}</pre>", 500

# ─────────────────────────────────────────────
# Customer auth
# ─────────────────────────────────────────────

@app.route("/")
def index():
    if "user_id" in session and session.get("role") == "customer":
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET","POST"])
def login():
    if "user_id" in session and session.get("role") == "customer":
        return redirect(url_for("dashboard"))
    error = None
    if request.method == "POST":
        email    = request.form.get("email","").strip().lower()
        password = request.form.get("password","")
        try:
            conn = get_db()
            cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("SELECT * FROM customers WHERE LOWER(email)=%s", (email,))
            customer = cur.fetchone()
            if customer and check_password(password, customer["password_hash"]):
                cur.execute("UPDATE customers SET last_login=%s WHERE id=%s",
                            (datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"), customer["id"]))
                conn.commit()
                cur.close(); conn.close()
                # Don't session.clear() — that would wipe any active admin session
                session["user_id"]   = customer["id"]
                session["user_name"] = customer["name"]
                session["role"]      = "customer"
                session.permanent    = True
                return redirect(url_for("dashboard"))
            cur.close(); conn.close()
        except Exception as e:
            return render_template("login.html", error=f"Database error: {e}", magic_msg=None, magic_error=False)
        error = "Invalid email or password. Please try again."
    return render_template("login.html", error=error, magic_msg=None, magic_error=False)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ─────────────────────────────────────────────
# Magic link (passwordless login)
# ─────────────────────────────────────────────

def fire_magic_link_webhook(name, email, magic_link_url):
    """POST magic link details to a dedicated HighLevel inbound webhook (silent fail)."""
    if not HIGHLEVEL_MAGIC_LINK_WEBHOOK_URL:
        return
    try:
        payload = json.dumps({
            "event":      "magic_link",
            "name":       name,
            "email":      email,
            "magic_link": magic_link_url,
            "expires_in": "30 minutes",
        }).encode("utf-8")
        req = urllib_req.Request(HIGHLEVEL_MAGIC_LINK_WEBHOOK_URL, data=payload, method="POST")
        req.add_header("Content-Type", "application/json")
        urllib_req.urlopen(req, timeout=5)
    except Exception:
        pass

@app.route("/request-magic-link", methods=["POST"])
def request_magic_link():
    email = request.form.get("email", "").strip().lower()
    if not email:
        return render_template("login.html", error=None,
                               magic_msg="Please enter your email address.", magic_error=True)
    try:
        conn = get_db()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Ensure magic_tokens table exists (customer_id is TEXT, not INTEGER)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS magic_tokens (
                id SERIAL PRIMARY KEY,
                customer_id TEXT NOT NULL,
                token TEXT UNIQUE NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                used BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        cur.execute("SELECT id, name, email FROM customers WHERE LOWER(email)=%s", (email,))
        customer = cur.fetchone()

        if customer:
            # Expire any existing unused tokens for this customer
            cur.execute("""
                UPDATE magic_tokens SET used=TRUE
                WHERE customer_id=%s AND used=FALSE
            """, (customer["id"],))

            token      = secrets.token_urlsafe(32)
            expires_at = datetime.utcnow() + timedelta(minutes=30)
            cur.execute("""
                INSERT INTO magic_tokens (customer_id, token, expires_at)
                VALUES (%s, %s, %s)
            """, (customer["id"], token, expires_at))
            conn.commit()

            magic_link_url = url_for("use_magic_link", token=token, _external=True)
            fire_magic_link_webhook(customer["name"], customer["email"], magic_link_url)

        cur.close(); conn.close()
    except Exception as e:
        return render_template("login.html", error=None,
                               magic_msg=f"Something went wrong: {e}", magic_error=True)

    # Always show the same success message (don't reveal if email exists)
    return render_template("login.html", error=None,
                           magic_msg="If that email is registered, a login link is on its way — check your inbox. It expires in 30 minutes.",
                           magic_error=False)

@app.route("/login/token/<token>")
def use_magic_link(token):
    try:
        conn = get_db()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT mt.id AS token_id, mt.expires_at, mt.used,
                   c.id AS customer_id, c.name, c.email
            FROM magic_tokens mt
            JOIN customers c ON c.id = mt.customer_id
            WHERE mt.token = %s
        """, (token,))
        row = cur.fetchone()

        if not row:
            cur.close(); conn.close()
            return render_template("login.html", error="This login link is invalid.",
                                   magic_msg=None, magic_error=False)
        if row["used"]:
            cur.close(); conn.close()
            return render_template("login.html", error="This login link has already been used.",
                                   magic_msg=None, magic_error=False)
        if datetime.utcnow() > row["expires_at"]:
            cur.close(); conn.close()
            return render_template("login.html",
                                   error="This login link has expired. Request a new one below.",
                                   magic_msg=None, magic_error=False)

        # Mark token used and update last login
        cur.execute("UPDATE magic_tokens SET used=TRUE WHERE id=%s", (row["token_id"],))
        cur.execute("UPDATE customers SET last_login=%s WHERE id=%s",
                    (datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"), row["customer_id"]))
        conn.commit()
        cur.close(); conn.close()

        session["user_id"]   = row["customer_id"]
        session["user_name"] = row["name"]
        session["role"]      = "customer"
        session.permanent    = True
        return redirect(url_for("dashboard"))

    except Exception as e:
        return render_template("login.html", error=f"Database error: {e}",
                               magic_msg=None, magic_error=False)

# ─────────────────────────────────────────────
# Customer dashboard
# ─────────────────────────────────────────────

@app.route("/dashboard")
@login_required
def dashboard():
    try:
        conn = get_db()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute("SELECT * FROM customers WHERE id=%s", (session["user_id"],))
        customer = cur.fetchone()
        if not customer:
            cur.close(); conn.close()
            session.clear()
            return redirect(url_for("login"))
        customer = dict(customer)
        assigned_ids = list(customer.get("assigned_dest_ids") or [])

        if assigned_ids:
            cur.execute("""
                SELECT * FROM destinations
                WHERE id = ANY(%s) AND status != 'archived'
                ORDER BY year, month
            """, (assigned_ids,))
            visible = []
            for r in cur.fetchall():
                d = row_to_dest(r)
                d["window_label"] = "Your Pick"
                d["window_slot"]  = "current"
                d["month_name"]   = MONTH_NAMES[d["month"] - 1]
                visible.append(d)
            is_assigned = True
        else:
            (prev_m, prev_y), (cur_m, cur_y), (next_m, next_y) = rolling_window()
            window_slots = [
                (cur_m,  cur_y,  "This Month",  "current"),
                (prev_m, prev_y, "Last Month",  "prev"),
                (next_m, next_y, "Coming Next", "next"),
            ]
            cur.execute("SELECT * FROM destinations WHERE status != 'archived' ORDER BY year, month")
            all_dests = {(r["month"], r["year"]): row_to_dest(r) for r in cur.fetchall()}
            visible = []
            for (wm, wy, label, slot) in window_slots:
                d = all_dests.get((wm, wy))
                if d:
                    d["window_label"] = label
                    d["window_slot"]  = slot
                    d["month_name"]   = MONTH_NAMES[wm - 1]
                else:
                    d = {
                        "id": f"placeholder_{wy}_{wm:02d}",
                        "name": "Coming Soon", "flag": "🌍",
                        "month": wm, "year": wy, "status": "coming_soon",
                        "files": {f: "" for f in FILE_FIELDS},
                        "window_label": label, "window_slot": slot,
                        "month_name": MONTH_NAMES[wm - 1],
                    }
                visible.append(d)
            is_assigned = False

        cur.execute("SELECT value FROM admin_settings WHERE key='engagement_folder_url'")
        row = cur.fetchone()
        engagement_folder_url = row["value"] if row else ""

        cur.close(); conn.close()
        ready = [d for d in visible if d["status"] == "ready"]
        return render_template("dashboard.html",
            customer=customer,
            destinations=visible,
            total_posts=len(ready) * 16,
            total_blogs=len(ready),
            is_assigned=is_assigned,
            month_names=MONTH_NAMES,
            engagement_folder_url=engagement_folder_url,
        )
    except Exception as e:
        return f"<h2>Dashboard error</h2><pre>{e}</pre>", 500

# ─────────────────────────────────────────────
# Customer API — change password
# ─────────────────────────────────────────────

@app.route("/api/change-password", methods=["POST"])
@login_required
def api_customer_change_password():
    body   = request.get_json(force=True, silent=True)
    current = body.get("current_password","")
    new_pw  = body.get("new_password","").strip()
    if len(new_pw) < 6:
        return jsonify({"error": "New password must be at least 6 characters."}), 400
    try:
        conn = get_db()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT password_hash FROM customers WHERE id=%s", (session["user_id"],))
        row = cur.fetchone()
        if not row or not check_password(current, row["password_hash"]):
            cur.close(); conn.close()
            return jsonify({"error": "Current password is incorrect."}), 403
        cur.execute("UPDATE customers SET password_hash=%s WHERE id=%s", (sha256(new_pw), session["user_id"]))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ─────────────────────────────────────────────
# Supplier offers — customer
# ─────────────────────────────────────────────

@app.route("/offers", methods=["GET"])
@login_required
def offers():
    try:
        conn = get_db()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM customers WHERE id=%s", (session["user_id"],))
        customer = dict(cur.fetchone())
        plan  = customer.get("plan") or "core"
        limit = OFFER_LIMITS.get(plan, 0)
        if limit == 0:
            cur.close(); conn.close()
            return redirect(url_for("dashboard"))
        today = date.today()
        cur.execute("""
            SELECT * FROM supplier_offers
            WHERE customer_id=%s AND month=%s AND year=%s
            ORDER BY submitted_at DESC
        """, (session["user_id"], today.month, today.year))
        my_offers = [dict(r) for r in cur.fetchall()]
        cur.close(); conn.close()
        success = request.args.get("success")
        error   = request.args.get("error")
        return render_template("offers.html",
            customer=customer, my_offers=my_offers,
            limit=limit, used=len(my_offers), plan=plan,
            current_month=MONTH_NAMES[today.month - 1],
            current_year=today.year,
            success=success, error=error,
        )
    except Exception as e:
        return f"<h2>Offers error</h2><pre>{e}</pre>", 500

@app.route("/offers", methods=["POST"])
@login_required
def submit_offer():
    try:
        conn = get_db()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT name, email, plan FROM customers WHERE id=%s", (session["user_id"],))
        cust  = cur.fetchone()
        plan  = (cust["plan"] if cust else None) or "core"
        cust_name  = cust["name"]  if cust else ""
        cust_email = cust["email"] if cust else ""
        limit = OFFER_LIMITS.get(plan, 0)
        if limit == 0:
            cur.close(); conn.close()
            return redirect(url_for("dashboard"))
        today = date.today()
        cur.execute("SELECT COUNT(*) as n FROM supplier_offers WHERE customer_id=%s AND month=%s AND year=%s",
                    (session["user_id"], today.month, today.year))
        used = cur.fetchone()["n"]
        if used >= limit:
            cur.close(); conn.close()
            return redirect(url_for("offers") + "?error=limit")
        offer_url = request.form.get("offer_url", "").strip()
        if not offer_url:
            cur.close(); conn.close()
            return redirect(url_for("offers") + "?error=url")
        caption  = request.form.get("caption", "").strip()
        notes    = request.form.get("notes", "").strip()

        # Validate images present — minimum 6 required
        files = request.files.getlist("images")
        valid_files = [f for f in files if f and f.filename and
                       (f.content_type in ALLOWED_IMAGE_TYPES)]
        if len(valid_files) < 6:
            cur.close(); conn.close()
            return redirect(url_for("offers") + "?error=images")

        offer_id = f"offer_{int(datetime.utcnow().timestamp() * 1000)}"

        # Handle image uploads (up to 6, images only)
        uploaded_urls = []
        for i, f in enumerate(valid_files):
            if not f or not f.filename:
                continue
            ct  = f.content_type or ""
            ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else "jpg"
            if ct not in ALLOWED_IMAGE_TYPES and not ct.startswith("image/"):
                continue
            path = f"{session['user_id']}/{offer_id}_{i}.{ext}"
            url  = upload_image(f.read(), path, ct)
            if url:
                uploaded_urls.append(url)

        cur.execute("""
            INSERT INTO supplier_offers
                (id, customer_id, submitted_at, month, year, offer_url, caption, notes, image_urls)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (offer_id, session["user_id"],
              datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),
              today.month, today.year,
              offer_url, caption, notes, uploaded_urls))
        submitted_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
        conn.commit(); cur.close(); conn.close()

        # Notify HighLevel — silent fail
        fire_hl_webhook(
            customer_name  = cust_name,
            customer_email = cust_email,
            plan           = plan,
            offer_url      = offer_url,
            caption        = caption,
            image_count    = len(uploaded_urls),
            submitted_at   = submitted_at,
        )

        return redirect(url_for("offers") + "?success=1")
    except Exception as e:
        return f"<h2>Submit error</h2><pre>{e}</pre>", 500

@app.route("/api/offers/<offer_id>", methods=["DELETE"])
@login_required
def api_delete_my_offer(offer_id):
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("DELETE FROM supplier_offers WHERE id=%s AND customer_id=%s",
                    (offer_id, session["user_id"]))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/admin/api/offers/<offer_id>", methods=["DELETE"])
@api_admin_required
def api_admin_delete_offer(offer_id):
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("DELETE FROM supplier_offers WHERE id=%s", (offer_id,))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/admin/api/offers/<offer_id>/generate-copy", methods=["POST"])
@api_admin_required
def api_generate_reel_copy(offer_id):
    """Call OpenAI to generate reel overlay copy from the offer's caption."""
    if not OPENAI_API_KEY:
        return jsonify({"error": "OpenAI API key (Render_Claude_Video_Reels) not set in Render environment variables."}), 500
    try:
        conn = get_db()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT caption, offer_url FROM supplier_offers WHERE id=%s", (offer_id,))
        offer = cur.fetchone()
        cur.close(); conn.close()
        if not offer:
            return jsonify({"error": "Offer not found."}), 404
        caption = offer["caption"] or ""
        prompt = f"""You are a social media copywriter for a travel agency creating short-form video reel overlay text.

From the supplier offer below, generate punchy overlay copy for a travel reel.

Return ONLY valid JSON — no markdown, no code fences — in exactly this format:
{{
  "headline": "max 6 words, bold benefit-led hook",
  "overlays": [
    "max 4 words",
    "max 4 words",
    "max 4 words",
    "max 4 words",
    "max 4 words"
  ],
  "cta": "max 5 words, action-oriented"
}}

Rules:
- Headline: the biggest selling point or saving — punchy, exciting
- Overlays: key facts only — destination, dates, duration, board basis, price/saving, family/pax info. Each line max 4 words.
- CTA: e.g. "Book before it goes!" or "Message us today!"
- No hashtags. No emojis. No full sentences.

Supplier offer:
{caption}"""

        payload = json.dumps({
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 300,
        }).encode("utf-8")

        req = urllib_req.Request(
            "https://api.openai.com/v1/chat/completions",
            data=payload, method="POST"
        )
        req.add_header("Authorization", f"Bearer {OPENAI_API_KEY}")
        req.add_header("Content-Type", "application/json")

        with urllib_req.urlopen(req, timeout=20) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        raw = result["choices"][0]["message"]["content"].strip()
        # Strip any accidental markdown fences
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        copy_data = json.loads(raw)
        return jsonify({"success": True, "copy": copy_data})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/admin/api/offers/<offer_id>/refine-caption", methods=["POST"])
@api_admin_required
def api_refine_caption(offer_id):
    """Use OpenAI to produce a clean, refined version of the supplier's post copy."""
    if not OPENAI_API_KEY:
        return jsonify({"error": "OpenAI API key (Render_Claude_Video_Reels) not set."}), 500
    try:
        conn = get_db()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT caption FROM supplier_offers WHERE id=%s", (offer_id,))
        offer = cur.fetchone()
        cur.close(); conn.close()
        if not offer:
            return jsonify({"error": "Offer not found."}), 404
        caption = offer["caption"] or ""
        if not caption:
            return jsonify({"error": "No post copy to refine."}), 400

        prompt = f"""You are editing a travel supplier's Facebook post for a UK travel agent to share with their followers.

Rewrite it so it's short, punchy, and engaging — the kind of post someone stops scrolling for. Apply every rule below without exception:

CONTENT RULES:
- Keep only the highlights that create excitement or show value: destination, duration, standout experiences (max 2–3), key inclusions, price, dates
- Do NOT reproduce or summarise any detailed itinerary text — if the original lists day-by-day activities or a long list of sights, drop it entirely and pick 1–2 of the most exciting highlights instead
- Keep all pricing, dates, and deposit information exactly as they appear in the original
- Do not add any facts that aren't in the original

FORMAT RULES:
- Remove all Unicode styled characters (𝗕𝗢𝗟𝗗, 𝘪𝘵𝘢𝘭𝘪𝘤, ｆｕｌｌｗｉｄｔｈ, etc.) — plain text only
- No ALL CAPS — normal sentence case throughout
- Maximum one emoji per line, at the very start of that line only
- NO blank lines between items within a list or section — list items run tight, one after the other
- Use a single blank line only to separate distinct sections (hook, inclusions list, dates, CTA)
- Structure: one-line hook → inclusions as a tight list → dates/prices → one CTA line
- No hashtags

Return ONLY the rewritten post — no explanation, no preamble, no surrounding quotes.

Original post:
{caption}"""

        payload = json.dumps({
            "model":       "gpt-4o-mini",
            "messages":    [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens":  500,
        }).encode("utf-8")

        req = urllib_req.Request(
            "https://api.openai.com/v1/chat/completions",
            data=payload, method="POST"
        )
        req.add_header("Authorization", f"Bearer {OPENAI_API_KEY}")
        req.add_header("Content-Type", "application/json")

        with urllib_req.urlopen(req, timeout=20) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        refined = result["choices"][0]["message"]["content"].strip()

        # Save refined caption to DB
        conn = get_db(); cur = conn.cursor()
        cur.execute("UPDATE supplier_offers SET refined_caption=%s WHERE id=%s", (refined, offer_id))
        conn.commit(); cur.close(); conn.close()

        return jsonify({"success": True, "refined_caption": refined})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/admin/api/offers/<offer_id>/auto-assign-slots", methods=["POST"])
@api_admin_required
def api_auto_assign_slots(offer_id):
    """Use GPT-4o vision to classify the offer's images and assign them to Freepik slots."""
    if not OPENAI_API_KEY:
        return jsonify({"error": "OpenAI API key (Render_Claude_Video_Reels) not set."}), 500
    body           = request.get_json(force=True, silent=True) or {}
    assigned_style = int(body.get("assigned_style", 0))
    if assigned_style not in STYLE_SEQUENCES:
        return jsonify({"error": "Pick a style (1–4) before auto-assigning."}), 400
    try:
        conn = get_db()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT image_urls FROM supplier_offers WHERE id=%s", (offer_id,))
        offer = cur.fetchone()
        cur.close(); conn.close()
        if not offer:
            return jsonify({"error": "Offer not found."}), 404
        image_urls = list(offer["image_urls"] or [])
        if not image_urls:
            return jsonify({"error": "No images found on this offer."}), 400

        # Build vision message — text prompt + one image block per image
        n = len(image_urls)
        image_blocks = [{"type": "text", "text": f"""You are classifying {n} travel images for a video reel slot assignment.

Look at each numbered image carefully and classify it into EXACTLY ONE of these slot types:

- Aerial: aerial/drone shot, overhead view — resort, bay, city, or pool from above
- LateralFly: wide outdoor scene — pool area, beach, garden, rice fields, open landscape
- CraneUp_Reveal: building exterior, temple ruins, landmark, tall structure, facade, archway
- LateralInterior: grand interior — hotel lobby, restaurant, bar, spa, large indoor hall
- DollyOut: bedroom, hotel suite, villa interior, bathroom
- LockedZoom: the single most dramatic image with strongest focal point — something a camera can push into (a lone figure in a doorway, a mountain peak, a dramatic archway, a standout hero image)

Return ONLY valid JSON — no markdown, no explanation — in exactly this format:
{{
  "classifications": [
    {{"image": 1, "slot": "SlotName", "description": "4–6 word description"}},
    {{"image": 2, "slot": "SlotName", "description": "4–6 word description"}}
  ]
}}

Rules:
- Each slot type should appear at most once. If two images could fit the same slot, pick the best match and assign the other to the next closest slot type.
- Every image must be classified — if there are more images than slot types, assign the extras to the slot type they fit best (duplicate slot names are allowed only as a last resort).
- Use only the exact slot names listed above (case-sensitive).
- Keep descriptions to 4–6 words max."""}]

        for i, url in enumerate(image_urls):
            image_blocks.append({
                "type": "image_url",
                "image_url": {"url": url, "detail": "low"}
            })

        payload = json.dumps({
            "model":       "gpt-4o",
            "messages":    [{"role": "user", "content": image_blocks}],
            "temperature": 0.2,
            "max_tokens":  500,
        }).encode("utf-8")

        req = urllib_req.Request(
            "https://api.openai.com/v1/chat/completions",
            data=payload, method="POST"
        )
        req.add_header("Authorization", f"Bearer {OPENAI_API_KEY}")
        req.add_header("Content-Type", "application/json")

        with urllib_req.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        raw = result["choices"][0]["message"]["content"].strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        classifications = json.loads(raw)["classifications"]

        # Build slot_assignments dict: slot_name → image_url
        slot_assignments = {}
        descriptions     = {}
        for item in classifications:
            idx  = int(item["image"]) - 1
            slot = item["slot"]
            desc = item.get("description", "")
            if 0 <= idx < len(image_urls) and slot not in slot_assignments:
                slot_assignments[slot] = image_urls[idx]
                descriptions[slot]     = desc

        # Build ordered result following the chosen style sequence
        sequence = STYLE_SEQUENCES[assigned_style]
        ordered  = []
        for clip_num, slot in enumerate(sequence, 1):
            img_url = slot_assignments.get(slot, "")
            # Determine which image number this is (1-based)
            img_num = None
            for item in classifications:
                if item["slot"] == slot:
                    img_num = item["image"]
                    break
            ordered.append({
                "clip":        clip_num,
                "slot":        slot,
                "image_url":   img_url,
                "image_num":   img_num,
                "description": descriptions.get(slot, ""),
            })

        # Persist to DB
        conn = get_db(); cur = conn.cursor()
        cur.execute("""
            UPDATE supplier_offers
               SET slot_assignments = %s,
                   assigned_style   = %s
             WHERE id = %s
        """, (json.dumps(slot_assignments), assigned_style, offer_id))
        conn.commit(); cur.close(); conn.close()

        return jsonify({
            "success":    True,
            "style":      assigned_style,
            "style_name": STYLE_NAMES[assigned_style],
            "clips":      ordered,
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ─────────────────────────────────────────────
# Admin auth
# ─────────────────────────────────────────────

@app.route("/admin/login", methods=["GET","POST"])
def admin_login():
    if session.get("admin_role") == "admin":
        return redirect(url_for("admin_panel"))
    error = None
    if request.method == "POST":
        username = request.form.get("username","").strip()
        password = request.form.get("password","")
        try:
            conn = get_db()
            cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("SELECT value FROM admin_settings WHERE key='username'")
            r = cur.fetchone(); stored_user = r["value"] if r else "admin"
            cur.execute("SELECT value FROM admin_settings WHERE key='password_hash'")
            r = cur.fetchone(); stored_hash = r["value"] if r else ""
            cur.close(); conn.close()
            if username == stored_user and check_password(password, stored_hash):
                # Use admin_role/admin_user_id so customer logins don't wipe admin session
                session["admin_user_id"] = "admin"
                session["admin_user_name"] = "Admin"
                session["admin_role"]    = "admin"
                session.permanent = True
                return redirect(url_for("admin_panel"))
        except Exception as e:
            return render_template("admin_login.html", error=f"Database error: {e}")
        error = "Invalid admin credentials."
    return render_template("admin_login.html", error=error)

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_user_id", None)
    session.pop("admin_user_name", None)
    session.pop("admin_role", None)
    return redirect(url_for("admin_login"))

# ─────────────────────────────────────────────
# Admin panel
# ─────────────────────────────────────────────

@app.route("/admin")
@admin_required
def admin_panel():
    try:
        conn = get_db()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute("SELECT * FROM customers ORDER BY joined_date")
        customers = []
        for r in cur.fetchall():
            c = dict(r)
            c['assigned_dest_ids'] = list(c.get('assigned_dest_ids') or [])
            customers.append(c)

        cur.execute("SELECT * FROM destinations ORDER BY year, month")
        all_dests = [row_to_dest(r) for r in cur.fetchall()]

        cur.execute("""
            SELECT o.*, c.name as customer_name, c.plan as customer_plan
            FROM supplier_offers o
            JOIN customers c ON o.customer_id = c.id
            ORDER BY o.year DESC, o.month DESC, o.submitted_at DESC
        """)
        all_offers = []
        for r in cur.fetchall():
            o = dict(r)
            try:
                o["slot_assignments"] = json.loads(o.get("slot_assignments") or "{}")
            except Exception:
                o["slot_assignments"] = {}
            o["assigned_style"]   = int(o.get("assigned_style") or 0)
            o["refined_caption"]  = o.get("refined_caption") or ""
            all_offers.append(o)

        cur.execute("SELECT value FROM admin_settings WHERE key='engagement_folder_url'")
        row = cur.fetchone()
        engagement_folder_url = row["value"] if row else ""

        cur.close(); conn.close()

        active_dests   = [d for d in all_dests if d['status'] != 'archived']
        archived_dests = [d for d in all_dests if d['status'] == 'archived']

        (prev_m, prev_y), (cur_m, cur_y), (next_m, next_y) = rolling_window()
        data = {
            "customers":             customers,
            "destinations":          active_dests,
            "archived_destinations": archived_dests,
            "all_destinations":      all_dests,
            "offers":                all_offers,
        }
        return render_template("admin.html",
            data=data,
            month_names=MONTH_NAMES,
            style_names=STYLE_NAMES,
            style_sequences=STYLE_SEQUENCES,
            current_year=date.today().year,
            rolling_window={
                "prev":    (prev_m, prev_y),
                "current": (cur_m,  cur_y),
                "next":    (next_m, next_y),
            },
            engagement_folder_url=engagement_folder_url,
        )
    except Exception as e:
        return f"<h2>Admin error</h2><pre>{e}</pre>", 500

# ─────────────────────────────────────────────
# Admin API — Customers
# ─────────────────────────────────────────────

@app.route("/admin/api/customers", methods=["POST"])
@api_admin_required
def api_add_customer():
    body     = request.get_json(force=True, silent=True)
    name     = body.get("name","").strip()
    email    = body.get("email","").strip().lower()
    password = body.get("password","").strip()
    if not all([name, email, password]):
        return jsonify({"error": "Name, email and password required."}), 400
    try:
        conn = get_db()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT id FROM customers WHERE LOWER(email)=%s", (email,))
        if cur.fetchone():
            cur.close(); conn.close()
            return jsonify({"error": "A customer with that email already exists."}), 400
        cur.execute("SELECT id FROM customers ORDER BY id")
        nums   = [int(r["id"].replace("cust_","")) for r in cur.fetchall() if r["id"].startswith("cust_")]
        new_id = f"cust_{(max(nums)+1 if nums else 1):03d}"
        joined = date.today().isoformat()
        cur.execute("""
            INSERT INTO customers (id,name,email,password_hash,joined_date,notes,assigned_dest_ids)
            VALUES (%s,%s,%s,%s,%s,'','{}')
        """, (new_id, name, email, sha256(password), joined))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"success": True, "customer": {
            "id": new_id, "name": name, "email": email, "joined_date": joined
        }})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/admin/api/customers/<cust_id>", methods=["DELETE"])
@api_admin_required
def api_delete_customer(cust_id):
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("DELETE FROM customers WHERE id=%s", (cust_id,))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/admin/api/customers/<cust_id>/password", methods=["PUT"])
@api_admin_required
def api_reset_password(cust_id):
    body = request.get_json(force=True, silent=True)
    pw   = body.get("password","").strip()
    if not pw:
        return jsonify({"error": "Password required."}), 400
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("UPDATE customers SET password_hash=%s WHERE id=%s", (sha256(pw), cust_id))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/admin/api/customers/<cust_id>/notes", methods=["PUT"])
@api_admin_required
def api_update_notes(cust_id):
    body  = request.get_json(force=True, silent=True)
    notes = body.get("notes","")
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("UPDATE customers SET notes=%s WHERE id=%s", (notes, cust_id))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/admin/api/customers/<cust_id>/plan", methods=["PUT"])
@api_admin_required
def api_update_plan(cust_id):
    body = request.get_json(force=True, silent=True)
    plan = body.get("plan", "core")
    if plan not in ["core","pro","managed"]:
        return jsonify({"error": "Invalid plan."}), 400
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("UPDATE customers SET plan=%s WHERE id=%s", (plan, cust_id))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/admin/api/customers/<cust_id>/supplier-reels", methods=["PUT"])
@api_admin_required
def api_update_supplier_reels(cust_id):
    body = request.get_json(force=True, silent=True)
    url  = body.get("supplier_reels_url", "").strip()
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("UPDATE customers SET supplier_reels_url=%s WHERE id=%s", (url, cust_id))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/admin/api/customers/<cust_id>/assign", methods=["PUT"])
@api_admin_required
def api_assign_dest(cust_id):
    body    = request.get_json(force=True, silent=True)
    dest_id = body.get("dest_id","")
    try:
        conn = get_db()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT assigned_dest_ids FROM customers WHERE id=%s", (cust_id,))
        row = cur.fetchone()
        if not row:
            cur.close(); conn.close()
            return jsonify({"error": "Customer not found."}), 404
        ids = list(row["assigned_dest_ids"] or [])
        if dest_id not in ids:
            ids.append(dest_id)
        cur.execute("UPDATE customers SET assigned_dest_ids=%s WHERE id=%s", (ids, cust_id))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"success": True, "assigned_dest_ids": ids})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/admin/api/customers/<cust_id>/unassign", methods=["PUT"])
@api_admin_required
def api_unassign_dest(cust_id):
    body    = request.get_json(force=True, silent=True)
    dest_id = body.get("dest_id","")
    try:
        conn = get_db()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT assigned_dest_ids FROM customers WHERE id=%s", (cust_id,))
        row = cur.fetchone()
        if not row:
            cur.close(); conn.close()
            return jsonify({"error": "Customer not found."}), 404
        ids = [i for i in (row["assigned_dest_ids"] or []) if i != dest_id]
        cur.execute("UPDATE customers SET assigned_dest_ids=%s WHERE id=%s", (ids, cust_id))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"success": True, "assigned_dest_ids": ids})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/admin/api/customers/<cust_id>/clear-assignments", methods=["PUT"])
@api_admin_required
def api_clear_assignments(cust_id):
    """Clear all assigned destinations for a customer in a single DB call."""
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("UPDATE customers SET assigned_dest_ids='{}' WHERE id=%s", (cust_id,))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"success": True, "assigned_dest_ids": []})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ─────────────────────────────────────────────
# Admin API — Destinations
# ─────────────────────────────────────────────

@app.route("/admin/api/destinations", methods=["POST"])
@api_admin_required
def api_add_destination():
    body   = request.get_json(force=True, silent=True)
    name   = body.get("name","").strip()
    flag   = body.get("flag","🌍").strip() or "🌍"
    month  = int(body.get("month", 1))
    year   = int(body.get("year", date.today().year))
    status = body.get("status","coming_soon")
    if not name:
        return jsonify({"error": "Destination name required."}), 400
    try:
        conn = get_db()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT id FROM destinations WHERE month=%s AND year=%s AND status!='archived'", (month,year))
        if cur.fetchone():
            cur.close(); conn.close()
            return jsonify({"error": f"An active destination for {MONTH_NAMES[month-1]} {year} already exists."}), 400
        dest_id = f"dest_{year}_{month:02d}"
        cur.execute("SELECT id FROM destinations WHERE id=%s", (dest_id,))
        if cur.fetchone():
            dest_id = f"dest_{year}_{month:02d}_b"
        cur.execute("""
            INSERT INTO destinations
                (id,name,flag,month,year,status,
                 social_media,blog,canva_guides,reels)
            VALUES (%s,%s,%s,%s,%s,%s,'','','','')
        """, (dest_id,name,flag,month,year,status))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"success": True, "destination": {
            "id": dest_id,"name": name,"flag": flag,"month": month,"year": year,"status": status
        }})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/admin/api/destinations/<dest_id>", methods=["DELETE"])
@api_admin_required
def api_delete_destination(dest_id):
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("DELETE FROM destinations WHERE id=%s", (dest_id,))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/admin/api/destinations/<dest_id>/files", methods=["PUT"])
@api_admin_required
def api_update_files(dest_id):
    body = request.get_json(force=True, silent=True)
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("""
            UPDATE destinations SET
                social_media=%s, blog=%s, canva_guides=%s, promo_assets=%s
            WHERE id=%s
        """, (body.get("social_media",""), body.get("blog",""),
              body.get("canva_guides",""),
              body.get("promo_assets",""), dest_id))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/admin/api/destinations/<dest_id>/status", methods=["PUT"])
@api_admin_required
def api_update_status(dest_id):
    body   = request.get_json(force=True, silent=True)
    status = body.get("status","ready")
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("UPDATE destinations SET status=%s WHERE id=%s", (status, dest_id))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/admin/api/destinations/<dest_id>/archive", methods=["PUT"])
@api_admin_required
def api_archive_destination(dest_id):
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("UPDATE destinations SET status='archived' WHERE id=%s", (dest_id,))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/admin/api/destinations/<dest_id>/reinstate", methods=["PUT"])
@api_admin_required
def api_reinstate_destination(dest_id):
    body  = request.get_json(force=True, silent=True)
    month = int(body.get("month", 1))
    year  = int(body.get("year", date.today().year))
    try:
        conn = get_db()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT id FROM destinations WHERE month=%s AND year=%s AND status!='archived' AND id!=%s",
                    (month, year, dest_id))
        if cur.fetchone():
            cur.close(); conn.close()
            return jsonify({"error": f"{MONTH_NAMES[month-1]} {year} already has an active destination."}), 400
        cur.execute("UPDATE destinations SET status='ready', month=%s, year=%s WHERE id=%s",
                    (month, year, dest_id))
        conn.commit()
        cur.execute("SELECT * FROM destinations WHERE id=%s", (dest_id,))
        d = row_to_dest(cur.fetchone())
        cur.close(); conn.close()
        return jsonify({"success": True, "destination": {
            "id": d["id"],"name": d["name"],"flag": d["flag"],
            "month": d["month"],"year": d["year"],"status": d["status"]
        }})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ─────────────────────────────────────────────
# Admin API — Admin password
# ─────────────────────────────────────────────

@app.route("/admin/api/admin-password", methods=["PUT"])
@api_admin_required
def api_change_admin_password():
    body    = request.get_json(force=True, silent=True)
    current = body.get("current_password","")
    new_pw  = body.get("new_password","").strip()
    if len(new_pw) < 6:
        return jsonify({"error": "New password must be at least 6 characters."}), 400
    try:
        conn = get_db()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT value FROM admin_settings WHERE key='password_hash'")
        row = cur.fetchone()
        if not row or not check_password(current, row["value"]):
            cur.close(); conn.close()
            return jsonify({"error": "Current password is incorrect."}), 403
        cur.execute("UPDATE admin_settings SET value=%s WHERE key='password_hash'", (sha256(new_pw),))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/admin/api/settings/engagement-folder", methods=["PUT"])
@api_admin_required
def api_update_engagement_folder():
    body = request.get_json(force=True, silent=True)
    url  = body.get("url", "").strip()
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("""
            INSERT INTO admin_settings (key, value) VALUES ('engagement_folder_url', %s)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
        """, (url,))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ─────────────────────────────────────────────
# DB migrations — run at startup
# ─────────────────────────────────────────────

def run_migrations():
    """Add new columns / tables to the DB if they don't already exist."""
    try:
        conn = get_db(); cur = conn.cursor()
        # 5-folder link structure (replaces the old 9-field layout)
        for col in ["social_media", "blog", "canva_guides", "reels", "promo_assets"]:
            cur.execute(f"ALTER TABLE destinations ADD COLUMN IF NOT EXISTS {col} TEXT DEFAULT ''")
        # Migrate old data into new columns (only where new columns are empty)
        cur.execute("""
            UPDATE destinations SET social_media = COALESCE(NULLIF(social_posts,''), NULLIF(images_folder,''), '')
            WHERE (social_media IS NULL OR social_media = '')
              AND (social_posts IS NOT NULL OR images_folder IS NOT NULL)
        """)
        cur.execute("""
            UPDATE destinations SET blog = COALESCE(NULLIF(blog_docx,''), NULLIF(promo_assets,''), '')
            WHERE (blog IS NULL OR blog = '')
              AND (blog_docx IS NOT NULL OR promo_assets IS NOT NULL)
        """)
        cur.execute("""
            UPDATE destinations SET canva_guides = COALESCE(NULLIF(canva_guide,''), NULLIF(guide_pdf,''), NULLIF(canva_carousel,''), NULLIF(canva_pinterest,''), '')
            WHERE (canva_guides IS NULL OR canva_guides = '')
              AND (canva_guide IS NOT NULL OR guide_pdf IS NOT NULL OR canva_carousel IS NOT NULL)
        """)
        cur.execute("""
            UPDATE destinations SET reels = COALESCE(NULLIF(video_reels,''), '')
            WHERE (reels IS NULL OR reels = '')
              AND video_reels IS NOT NULL
        """)
        # Magic tokens table — drop and recreate if customer_id is wrong type (INTEGER vs TEXT)
        cur.execute("""
            SELECT data_type FROM information_schema.columns
            WHERE table_name='magic_tokens' AND column_name='customer_id'
        """)
        row = cur.fetchone()
        if row and row[0] != 'text':
            cur.execute("DROP TABLE magic_tokens")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS magic_tokens (
                id SERIAL PRIMARY KEY,
                customer_id TEXT NOT NULL,
                token TEXT UNIQUE NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                used BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        conn.commit(); cur.close(); conn.close()
    except Exception:
        pass  # Never block startup

try:
    run_migrations()
except Exception:
    pass

# Run independently so a failure in run_migrations() can't block these
def run_migrations_extra():
    """Independent migrations that must not be blocked by run_migrations failures."""
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("ALTER TABLE customers ADD COLUMN IF NOT EXISTS supplier_reels_url TEXT DEFAULT ''")
        cur.execute("ALTER TABLE supplier_offers ADD COLUMN IF NOT EXISTS slot_assignments TEXT DEFAULT '{}'")
        cur.execute("ALTER TABLE supplier_offers ADD COLUMN IF NOT EXISTS assigned_style INTEGER DEFAULT 0")
        cur.execute("ALTER TABLE supplier_offers ADD COLUMN IF NOT EXISTS refined_caption TEXT DEFAULT ''")
        # Ensure admin_settings has a unique constraint on key so ON CONFLICT works
        cur.execute("""
            DO $$ BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'admin_settings_key_unique'
                ) THEN
                    ALTER TABLE admin_settings ADD CONSTRAINT admin_settings_key_unique UNIQUE (key);
                END IF;
            END $$;
        """)
        # Seed engagement_folder_url row if it doesn't exist
        cur.execute("""
            INSERT INTO admin_settings (key, value) VALUES ('engagement_folder_url', '')
            ON CONFLICT (key) DO NOTHING
        """)
        conn.commit(); cur.close(); conn.close()
    except Exception:
        pass

try:
    run_migrations_extra()
except Exception:
    pass

# ─────────────────────────────────────────────
# Run
# ─────────────────────────────────────────────

if __name__ == "__main__":
    port  = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG","false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
