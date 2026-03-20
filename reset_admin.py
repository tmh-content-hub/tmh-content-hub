"""
Run this once to reset the admin password.
Usage: python3 reset_admin.py
"""
import json, bcrypt, os

DATA_FILE = os.path.join(os.path.dirname(__file__), "data.json")

with open(DATA_FILE, "r") as f:
    data = json.load(f)

new_password = "tmh-admin-2024"
hashed = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

data["admin"]["username"] = "admin"
data["admin"]["password_hash"] = hashed

with open(DATA_FILE, "w") as f:
    json.dump(data, f, indent=2)

print("✅ Admin password reset successfully.")
print("   Username: admin")
print("   Password: tmh-admin-2024")
