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

        cur.close(); conn.close()
        ready = [d for d in visible if d["status"] == "ready"]
        return render_template("dashboard.html",
            customer=customer,
            destinations=visible,
            total_posts=len(ready) * 16,
            total_blogs=len(ready),
            is_assigned=is_assigned,
            month_names=MONTH_NAMES,
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
        all_offers = [dict(r) for r in cur.fetchall()]
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
            current_year=date.today().year,
            rolling_window={
                "prev":    (prev_m, prev_y),
                "current": (cur_m,  cur_y),
                "next":    (next_m, next_y),
            },
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
                social_media=%s, blog=%s, canva_guides=%s, reels=%s, promo_assets=%s
            WHERE id=%s
        """, (body.get("social_media",""), body.get("blog",""),
              body.get("canva_guides",""), body.get("reels",""),
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
