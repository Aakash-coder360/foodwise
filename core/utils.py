import re
import base64
import io
from datetime import datetime
import matplotlib.pyplot as plt
from .database import get_conn

def is_valid_date(date_str):
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False

def is_valid_name(name):
    return bool(re.match(r"^[a-zA-Z0-9\s\-]+$", name))

def expiry_status(expiry):
    if not expiry:
        return "— (non-perishable)", "gray"
    try:
        d = datetime.strptime(expiry, "%Y-%m-%d").date()
    except Exception:
        return "invalid date", "red"
    days = (d - datetime.now().date()).days
    if days < 0: return f"EXPIRED {abs(days)}d", "red"
    if days == 0: return "TODAY", "red"
    if days <= 7: return f"{days}d", "orange"
    return f"{days}d", "green"

def generate_chart_base64():
    conn = get_conn()
    rows = conn.execute("SELECT category, COUNT(*) as n FROM items GROUP BY category").fetchall()
    conn.close()
    if not rows:
        return ""
    
    labels = [r["category"] for r in rows]
    values = [r["n"] for r in rows]

    plt.figure(figsize=(6, 3))
    plt.bar(labels, values, color="#10B981")
    plt.title("Stock by Category")
    plt.tight_layout()
    
    img = io.BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    plt.close()
    return base64.b64encode(img.getvalue()).decode()