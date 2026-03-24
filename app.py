import os
import json
import hashlib
import psycopg2
import psycopg2.extras
from datetime import date
from functools import wraps
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, jsonify
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "tmh-dev-secret-change-in-production")
DATABASE_URL = os.environ.get("DATABASE_URL", "")
DATA_FILE = os.path.join(os.path.dirname(__file__), "data.json")

MONTH_NAMES = ["January","February","March","April","May","June",
               "July","August","September","October","November","December"]

FILE_FIELDS = ["blog_docx","social_posts","promo_assets","guide_pdf",
               "images_folder","canva_guide","canva_carousel","canva_pinterest"]

# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def get_db():
    url = DATABASE_URL
    if url and 'sslmode' not in url:
        url += ('&' if '?' in url else '?') + 'sslmode=require'
    return psycopg2.connect(url)

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
        if "user_id" not in session or session.get("role") != "admin":
            return redirect(url_for("admin_login"))
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
            cur.close(); conn.close()
            if customer and check_password(password, customer["password_hash"]):
                session.clear()
                session["user_id"]   = customer["id"]
                session["user_name"] = customer["name"]
                session["role"]      = "customer"
                return redirect(url_for("dashboard"))
        except Exception as e:
            return render_template("login.html", error=f"Database error: {e}")
        error = "Invalid email or password. Please try again."
    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

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
        )
    except Exception as e:
        return f"<h2>Dashboard error</h2><pre>{e}</pre>", 500

# ─────────────────────────────────────────────
# Customer API — change password
# ─────────────────────────────────────────────

@app.route("/api/change-password", methods=["POST"])
@login_required
def api_customer_change_password():
    body   = request.get_json()
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
# Admin auth
# ─────────────────────────────────────────────

@app.route("/admin/login", methods=["GET","POST"])
def admin_login():
    if "user_id" in session and session.get("role") == "admin":
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
                session.clear()
                session["user_id"]   = "admin"
                session["user_name"] = "Admin"
                session["role"]      = "admin"
                return redirect(url_for("admin_panel"))
        except Exception as e:
            return render_template("admin_login.html", error=f"Database error: {e}")
        error = "Invalid admin credentials."
    return render_template("admin_login.html", error=error)

@app.route("/admin/logout")
def admin_logout():
    session.clear()
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
        all_dests    = [row_to_dest(r) for r in cur.fetchall()]
        cur.close(); conn.close()

        active_dests   = [d for d in all_dests if d['status'] != 'archived']
        archived_dests = [d for d in all_dests if d['status'] == 'archived']

        (prev_m, prev_y), (cur_m, cur_y), (next_m, next_y) = rolling_window()
        data = {
            "customers":           customers,
            "destinations":        active_dests,
            "archived_destinations": archived_dests,
            "all_destinations":    all_dests,
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
@admin_required
def api_add_customer():
    body     = request.get_json()
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
@admin_required
def api_delete_customer(cust_id):
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("DELETE FROM customers WHERE id=%s", (cust_id,))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/admin/api/customers/<cust_id>/password", methods=["PUT"])
@admin_required
def api_reset_password(cust_id):
    body = request.get_json()
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
@admin_required
def api_update_notes(cust_id):
    body  = request.get_json()
    notes = body.get("notes","")
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("UPDATE customers SET notes=%s WHERE id=%s", (notes, cust_id))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/admin/api/customers/<cust_id>/assign", methods=["PUT"])
@admin_required
def api_assign_dest(cust_id):
    body    = request.get_json()
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
@admin_required
def api_unassign_dest(cust_id):
    body    = request.get_json()
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

# ─────────────────────────────────────────────
# Admin API — Destinations
# ─────────────────────────────────────────────

@app.route("/admin/api/destinations", methods=["POST"])
@admin_required
def api_add_destination():
    body   = request.get_json()
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
                 blog_docx,social_posts,promo_assets,guide_pdf,
                 images_folder,canva_guide,canva_carousel,canva_pinterest)
            VALUES (%s,%s,%s,%s,%s,%s,'','','','','','','','')
        """, (dest_id,name,flag,month,year,status))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"success": True, "destination": {
            "id": dest_id,"name": name,"flag": flag,"month": month,"year": year,"status": status
        }})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/admin/api/destinations/<dest_id>", methods=["DELETE"])
@admin_required
def api_delete_destination(dest_id):
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("DELETE FROM destinations WHERE id=%s", (dest_id,))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/admin/api/destinations/<dest_id>/files", methods=["PUT"])
@admin_required
def api_update_files(dest_id):
    body = request.get_json()
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("""
            UPDATE destinations SET
                blog_docx=%s, social_posts=%s, promo_assets=%s, guide_pdf=%s,
                images_folder=%s, canva_guide=%s, canva_carousel=%s, canva_pinterest=%s
            WHERE id=%s
        """, (body.get("blog_docx",""), body.get("social_posts",""), body.get("promo_assets",""),
              body.get("guide_pdf",""), body.get("images_folder",""), body.get("canva_guide",""),
              body.get("canva_carousel",""), body.get("canva_pinterest",""), dest_id))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/admin/api/destinations/<dest_id>/status", methods=["PUT"])
@admin_required
def api_update_status(dest_id):
    body   = request.get_json()
    status = body.get("status","ready")
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("UPDATE destinations SET status=%s WHERE id=%s", (status, dest_id))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/admin/api/destinations/<dest_id>/archive", methods=["PUT"])
@admin_required
def api_archive_destination(dest_id):
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("UPDATE destinations SET status='archived' WHERE id=%s", (dest_id,))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/admin/api/destinations/<dest_id>/reinstate", methods=["PUT"])
@admin_required
def api_reinstate_destination(dest_id):
    body  = request.get_json()
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
@admin_required
def api_change_admin_password():
    body    = request.get_json()
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
# Run
# ─────────────────────────────────────────────

if __name__ == "__main__":
    port  = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG","false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
