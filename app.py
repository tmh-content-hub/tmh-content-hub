import os
import json
import hashlib
import bcrypt
from datetime import date
from functools import wraps
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, jsonify
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "tmh-dev-secret-change-in-production")

DATA_FILE = os.path.join(os.path.dirname(__file__), "data.json")

MONTH_NAMES = ["January","February","March","April","May","June",
               "July","August","September","October","November","December"]

# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def load_data():
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def check_password(plain, stored):
    """Check plain text password against stored hash (bcrypt or sha256)."""
    if stored.startswith("$2b$") or stored.startswith("$2a$"):
        return bcrypt.checkpw(plain.encode("utf-8"), stored.encode("utf-8"))
    return sha256(plain) == stored

def rolling_window():
    """Return (prev, current, next) as (month, year) tuples."""
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
# Customer auth
# ─────────────────────────────────────────────

@app.route("/")
def index():
    if "user_id" in session and session.get("role") == "customer":
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session and session.get("role") == "customer":
        return redirect(url_for("dashboard"))
    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        data = load_data()
        customer = next((c for c in data["customers"] if c["email"].lower() == email), None)
        if customer and check_password(password, customer["password_hash"]):
            session.clear()
            session["user_id"] = customer["id"]
            session["user_name"] = customer["name"]
            session["role"] = "customer"
            return redirect(url_for("dashboard"))
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
    data = load_data()
    customer = next((c for c in data["customers"] if c["id"] == session["user_id"]), None)
    if not customer:
        session.clear()
        return redirect(url_for("login"))

    (prev_m, prev_y), (cur_m, cur_y), (next_m, next_y) = rolling_window()

    window_map = {
        (prev_m, prev_y): ("Last Month",   "prev"),
        (cur_m,  cur_y):  ("This Month",   "current"),
        (next_m, next_y): ("Coming Next",  "next"),
    }

    dest_lookup = {(d["month"], d["year"]): d for d in data["destinations"]}

    visible = []
    for (wm, wy), (label, slot) in window_map.items():
        dest = dest_lookup.get((wm, wy))
        if dest:
            d = dict(dest)
            d["window_label"] = label
            d["window_slot"] = slot
            d["month_name"] = MONTH_NAMES[wm - 1]
        else:
            # Placeholder for months with no destination configured yet
            d = {
                "id": f"placeholder_{wy}_{wm:02d}",
                "name": "Coming Soon",
                "flag": "🌍",
                "month": wm,
                "year": wy,
                "status": "coming_soon",
                "files": {},
                "window_label": label,
                "window_slot": slot,
                "month_name": MONTH_NAMES[wm - 1],
            }
        visible.append(d)

    ready = [d for d in visible if d["status"] == "ready"]
    total_posts = len(ready) * 16
    total_blogs = len(ready)

    return render_template(
        "dashboard.html",
        customer=customer,
        destinations=visible,
        total_posts=total_posts,
        total_blogs=total_blogs,
    )

# ─────────────────────────────────────────────
# Customer API — change password
# ─────────────────────────────────────────────

@app.route("/api/change-password", methods=["POST"])
@login_required
def api_customer_change_password():
    data = load_data()
    body = request.get_json()
    current = body.get("current_password", "")
    new_pw  = body.get("new_password", "").strip()

    if not new_pw or len(new_pw) < 6:
        return jsonify({"error": "New password must be at least 6 characters."}), 400

    customer = next((c for c in data["customers"] if c["id"] == session["user_id"]), None)
    if not customer:
        return jsonify({"error": "Not found."}), 404

    if not check_password(current, customer["password_hash"]):
        return jsonify({"error": "Current password is incorrect."}), 403

    customer["password_hash"] = sha256(new_pw)
    save_data(data)
    return jsonify({"success": True})

# ─────────────────────────────────────────────
# Admin auth
# ─────────────────────────────────────────────

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if "user_id" in session and session.get("role") == "admin":
        return redirect(url_for("admin_panel"))
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        data = load_data()
        admin = data.get("admin", {})
        if username == admin.get("username") and check_password(password, admin.get("password_hash", "")):
            session.clear()
            session["user_id"] = "admin"
            session["user_name"] = "Admin"
            session["role"] = "admin"
            return redirect(url_for("admin_panel"))
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
    data = load_data()
    (prev_m, prev_y), (cur_m, cur_y), (next_m, next_y) = rolling_window()
    return render_template(
        "admin.html",
        data=data,
        month_names=MONTH_NAMES,
        current_year=date.today().year,
        rolling_window={"prev": (prev_m, prev_y), "current": (cur_m, cur_y), "next": (next_m, next_y)},
    )

# ─────────────────────────────────────────────
# Admin API — Customers
# ─────────────────────────────────────────────

@app.route("/admin/api/customers", methods=["POST"])
@admin_required
def api_add_customer():
    data = load_data()
    body = request.get_json()
    name     = body.get("name", "").strip()
    email    = body.get("email", "").strip().lower()
    password = body.get("password", "").strip()

    if not name or not email or not password:
        return jsonify({"error": "Name, email and password are required."}), 400
    if any(c["email"].lower() == email for c in data["customers"]):
        return jsonify({"error": "A customer with that email already exists."}), 400

    nums = [int(c["id"].replace("cust_", "")) for c in data["customers"] if c["id"].startswith("cust_")]
    new_id = f"cust_{(max(nums) + 1 if nums else 1):03d}"

    new_customer = {
        "id": new_id,
        "name": name,
        "email": email,
        "password_hash": sha256(password),
        "joined_date": date.today().isoformat(),
        "notes": ""
    }
    data["customers"].append(new_customer)
    save_data(data)
    return jsonify({"success": True, "customer": {
        "id": new_id, "name": name, "email": email,
        "joined_date": new_customer["joined_date"]
    }})

@app.route("/admin/api/customers/<cust_id>", methods=["DELETE"])
@admin_required
def api_delete_customer(cust_id):
    data = load_data()
    data["customers"] = [c for c in data["customers"] if c["id"] != cust_id]
    save_data(data)
    return jsonify({"success": True})

@app.route("/admin/api/customers/<cust_id>/password", methods=["PUT"])
@admin_required
def api_reset_password(cust_id):
    data = load_data()
    body = request.get_json()
    password = body.get("password", "").strip()
    if not password:
        return jsonify({"error": "Password required."}), 400
    for c in data["customers"]:
        if c["id"] == cust_id:
            c["password_hash"] = sha256(password)
            save_data(data)
            return jsonify({"success": True})
    return jsonify({"error": "Customer not found."}), 404

@app.route("/admin/api/customers/<cust_id>/notes", methods=["PUT"])
@admin_required
def api_update_notes(cust_id):
    data = load_data()
    body = request.get_json()
    notes = body.get("notes", "")
    for c in data["customers"]:
        if c["id"] == cust_id:
            c["notes"] = notes
            save_data(data)
            return jsonify({"success": True})
    return jsonify({"error": "Customer not found."}), 404

# ─────────────────────────────────────────────
# Admin API — Destinations
# ─────────────────────────────────────────────

@app.route("/admin/api/destinations", methods=["POST"])
@admin_required
def api_add_destination():
    data = load_data()
    body = request.get_json()
    name   = body.get("name", "").strip()
    flag   = body.get("flag", "🌍").strip()
    month  = int(body.get("month", 1))
    year   = int(body.get("year", date.today().year))
    status = body.get("status", "coming_soon")

    if not name:
        return jsonify({"error": "Destination name is required."}), 400
    if any(d["month"] == month and d["year"] == year for d in data["destinations"]):
        return jsonify({"error": f"A destination for {MONTH_NAMES[month-1]} {year} already exists."}), 400

    dest_id = f"dest_{year}_{month:02d}"
    new_dest = {
        "id": dest_id,
        "name": name,
        "flag": flag,
        "month": month,
        "year": year,
        "status": status,
        "files": {
            "blog_docx": "", "social_posts": "", "promo_assets": "",
            "guide_pdf": "", "images_folder": "",
            "canva_guide": "", "canva_carousel": "", "canva_pinterest": ""
        }
    }
    data["destinations"].append(new_dest)
    data["destinations"].sort(key=lambda d: (d["year"], d["month"]))
    save_data(data)
    return jsonify({"success": True, "destination": {
        "id": dest_id, "name": name, "flag": flag, "month": month, "year": year, "status": status
    }})

@app.route("/admin/api/destinations/<dest_id>", methods=["DELETE"])
@admin_required
def api_delete_destination(dest_id):
    data = load_data()
    data["destinations"] = [d for d in data["destinations"] if d["id"] != dest_id]
    save_data(data)
    return jsonify({"success": True})

@app.route("/admin/api/destinations/<dest_id>/files", methods=["PUT"])
@admin_required
def api_update_files(dest_id):
    data = load_data()
    body = request.get_json()
    for d in data["destinations"]:
        if d["id"] == dest_id:
            for field in ["blog_docx","social_posts","promo_assets","guide_pdf",
                          "images_folder","canva_guide","canva_carousel","canva_pinterest"]:
                if field in body:
                    d["files"][field] = body[field]
            save_data(data)
            return jsonify({"success": True})
    return jsonify({"error": "Destination not found."}), 404

@app.route("/admin/api/destinations/<dest_id>/status", methods=["PUT"])
@admin_required
def api_update_status(dest_id):
    data = load_data()
    body = request.get_json()
    status = body.get("status", "ready")
    for d in data["destinations"]:
        if d["id"] == dest_id:
            d["status"] = status
            save_data(data)
            return jsonify({"success": True})
    return jsonify({"error": "Destination not found."}), 404

# ─────────────────────────────────────────────
# Admin API — Admin password
# ─────────────────────────────────────────────

@app.route("/admin/api/admin-password", methods=["PUT"])
@admin_required
def api_change_admin_password():
    data = load_data()
    body = request.get_json()
    current = body.get("current_password", "")
    new_pw  = body.get("new_password", "").strip()

    if not new_pw or len(new_pw) < 6:
        return jsonify({"error": "New password must be at least 6 characters."}), 400

    admin = data.get("admin", {})
    if not check_password(current, admin.get("password_hash", "")):
        return jsonify({"error": "Current password is incorrect."}), 403

    data["admin"]["password_hash"] = sha256(new_pw)
    save_data(data)
    return jsonify({"success": True})

# ─────────────────────────────────────────────
# Run
# ─────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
