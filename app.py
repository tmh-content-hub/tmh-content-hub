import os
import json
import hashlib
import bcrypt
from functools import wraps
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, jsonify, flash
)

def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "tmh-dev-secret-change-in-production")

DATA_FILE = os.path.join(os.path.dirname(__file__), "data.json")

# ─────────────────────────────────────────────
# Data helpers
# ─────────────────────────────────────────────

def load_data():
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ─────────────────────────────────────────────
# Auth decorators
# ─────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
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
# Customer auth routes
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
        password = request.form.get("password", "").encode("utf-8")
        data = load_data()

        customer = next(
            (c for c in data["customers"] if c["email"].lower() == email), None
        )
        if customer and bcrypt.checkpw(password, customer["password_hash"].encode("utf-8")):
            session.clear()
            session["user_id"] = customer["id"]
            session["user_name"] = customer["name"]
            session["role"] = "customer"
            return redirect(url_for("dashboard"))
        else:
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
    customer = next(
        (c for c in data["customers"] if c["id"] == session["user_id"]), None
    )
    if not customer:
        session.clear()
        return redirect(url_for("login"))

    # Build destination list in order, with "new" badge on most recently added
    dest_ids = customer.get("destinations", [])
    all_dests = {d["id"]: d for d in data["destinations"]}

    assigned = []
    for i, did in enumerate(dest_ids):
        dest = all_dests.get(did)
        if dest:
            d = dict(dest)
            # Most recently added = last in list → badge "New"
            d["badge"] = "New" if i == len(dest_ids) - 1 and len(dest_ids) > 0 else "Ready"
            assigned.append(d)

    # Coming soon destinations (global pipeline items not assigned to this customer)
    coming_soon = [
        d for d in data["destinations"]
        if d.get("status") == "coming_soon" and d["id"] not in dest_ids
    ]

    total_posts = len(assigned) * 16
    total_blogs = len(assigned)

    return render_template(
        "dashboard.html",
        customer=customer,
        destinations=assigned,
        coming_soon=coming_soon,
        total_posts=total_posts,
        total_blogs=total_blogs,
    )

# ─────────────────────────────────────────────
# Admin auth routes
# ─────────────────────────────────────────────

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if "user_id" in session and session.get("role") == "admin":
        return redirect(url_for("admin_panel"))

    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").encode("utf-8")
        data = load_data()
        admin = data.get("admin", {})

        stored = admin.get("password_hash", "")
        # Support both SHA256 hex hashes and plain bcrypt hashes
        if stored.startswith("$2b$") or stored.startswith("$2a$"):
            pw_ok = bcrypt.checkpw(password, stored.encode("utf-8"))
        else:
            pw_ok = sha256(password.decode("utf-8")) == stored

        if (username == admin.get("username") and pw_ok):
            session.clear()
            session["user_id"] = "admin"
            session["user_name"] = "Admin"
            session["role"] = "admin"
            return redirect(url_for("admin_panel"))
        else:
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
    return render_template("admin.html", data=data)

# ─────────────────────────────────────────────
# Admin API — Customers
# ─────────────────────────────────────────────

@app.route("/admin/api/customers", methods=["POST"])
@admin_required
def api_add_customer():
    data = load_data()
    body = request.get_json()
    name = body.get("name", "").strip()
    email = body.get("email", "").strip().lower()
    password = body.get("password", "").strip()

    if not name or not email or not password:
        return jsonify({"error": "Name, email and password are required."}), 400

    if any(c["email"].lower() == email for c in data["customers"]):
        return jsonify({"error": "A customer with that email already exists."}), 400

    pw_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    # Generate a simple incremental ID
    existing_ids = [c["id"] for c in data["customers"]]
    nums = [int(i.replace("cust_", "")) for i in existing_ids if i.startswith("cust_")]
    next_num = max(nums) + 1 if nums else 1
    new_id = f"cust_{next_num:03d}"

    new_customer = {
        "id": new_id,
        "name": name,
        "email": email,
        "password_hash": pw_hash,
        "destinations": []
    }
    data["customers"].append(new_customer)
    save_data(data)
    return jsonify({"success": True, "customer": {"id": new_id, "name": name, "email": email}})

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
            c["password_hash"] = bcrypt.hashpw(
                password.encode("utf-8"), bcrypt.gensalt()
            ).decode("utf-8")
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
    name = body.get("name", "").strip()
    flag = body.get("flag", "🌍").strip()
    status = body.get("status", "ready")

    if not name:
        return jsonify({"error": "Destination name is required."}), 400

    # Generate ID from name
    base_id = "dest_" + name.lower().replace(" ", "_").replace("-", "_")
    # Ensure unique
    existing = [d["id"] for d in data["destinations"]]
    dest_id = base_id
    counter = 2
    while dest_id in existing:
        dest_id = f"{base_id}_{counter}"
        counter += 1

    new_dest = {
        "id": dest_id,
        "name": name,
        "flag": flag,
        "status": status,
        "files": {
            "blog_docx": "",
            "social_posts": "",
            "promo_assets": "",
            "guide_pdf": "",
            "images_folder": "",
            "canva_guide": "",
            "canva_carousel": "",
            "canva_pinterest": ""
        }
    }
    data["destinations"].append(new_dest)
    save_data(data)
    return jsonify({"success": True, "destination": {"id": dest_id, "name": name, "flag": flag}})

@app.route("/admin/api/destinations/<dest_id>", methods=["DELETE"])
@admin_required
def api_delete_destination(dest_id):
    data = load_data()
    data["destinations"] = [d for d in data["destinations"] if d["id"] != dest_id]
    # Also remove from all customers
    for c in data["customers"]:
        c["destinations"] = [d for d in c.get("destinations", []) if d != dest_id]
    save_data(data)
    return jsonify({"success": True})

# ─────────────────────────────────────────────
# Admin API — Assign destinations + links
# ─────────────────────────────────────────────

@app.route("/admin/api/assign", methods=["POST"])
@admin_required
def api_assign():
    """Assign or unassign a destination for a customer."""
    data = load_data()
    body = request.get_json()
    cust_id = body.get("customer_id")
    dest_id = body.get("destination_id")
    assigned = body.get("assigned", False)  # True = add, False = remove

    for c in data["customers"]:
        if c["id"] == cust_id:
            if assigned and dest_id not in c["destinations"]:
                c["destinations"].append(dest_id)
            elif not assigned and dest_id in c["destinations"]:
                c["destinations"].remove(dest_id)
            save_data(data)
            return jsonify({"success": True})

    return jsonify({"error": "Customer not found."}), 404

@app.route("/admin/api/destinations/<dest_id>/files", methods=["PUT"])
@admin_required
def api_update_files(dest_id):
    """Update all file/link URLs for a destination."""
    data = load_data()
    body = request.get_json()

    for d in data["destinations"]:
        if d["id"] == dest_id:
            fields = [
                "blog_docx", "social_posts", "promo_assets",
                "guide_pdf", "images_folder",
                "canva_guide", "canva_carousel", "canva_pinterest"
            ]
            for field in fields:
                if field in body:
                    d["files"][field] = body[field]
            save_data(data)
            return jsonify({"success": True})

    return jsonify({"error": "Destination not found."}), 404

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
    stored = admin.get("password_hash", "")

    # Verify current password
    if stored.startswith("$2b$") or stored.startswith("$2a$"):
        ok = bcrypt.checkpw(current.encode("utf-8"), stored.encode("utf-8"))
    else:
        ok = sha256(current) == stored

    if not ok:
        return jsonify({"error": "Current password is incorrect."}), 403

    data["admin"]["password_hash"] = sha256(new_pw)
    save_data(data)
    return jsonify({"success": True})

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
# Run
# ─────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
