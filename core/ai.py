import json
from google import genai
from .logger import logger
from .database import get_conn, get_monthly_report, get_frequent_items

CONFIG_FILE = "config.txt"
GEMINI_MODEL = "gemini-3.8-flash"  # Updated to stable model

def load_api_key():
    try:
        with open(CONFIG_FILE, "r") as f:
            for line in f:
                if "GEMINI_API_KEY" in line:
                    # Safe parsing
                    parts = line.strip().split("=")
                    if len(parts) >= 2:
                        return "=".join(parts[1:]).strip()
    except FileNotFoundError:
        return None
    except Exception as e:
        logger.error(f"Error reading key: {e}")
        return None
    return None

def ask_gemini(question):
    key = load_api_key()
    if not key:
        return None, "No API key found in config.txt"
    try:
        client = genai.Client(api_key=key)
        prompt = f"You are FoodWise, a smart grocery assistant. Answer concisely. Question: {question}"
        resp = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        # Direct text return
        if resp.text:
            return resp.text.strip(), None
        return None, "Empty response from Gemini"
    except Exception as e:
        error_msg = f"Gemini API Error: {str(e)}"
        logger.error(error_msg)
        return None, error_msg

def ask_offline(question):
    q = question.lower().strip()
    conn = get_conn()
    
    if "expir" in q:
        rows = conn.execute("SELECT name, expiry_date FROM items WHERE expiry_date IS NOT NULL AND date(expiry_date) <= date('now', '+7 day')").fetchall()
        conn.close()
        if not rows: return "Everything is fresh! Nothing is expiring soon."
        return "Expiring soon:\n" + "\n".join([f"• {r['name']} (Expires: {r['expiry_date']})" for r in rows])

    if "spend" in q or "spent" in q:
        rep = get_monthly_report()
        conn.close()
        return f"Total spend for this month: ₹{rep['total']}"

    if "frequent" in q or "buy most" in q:
        freq = get_frequent_items()
        conn.close()
        if not freq: return "No purchase history found yet."
        return "Most frequently purchased items:\n" + "\n".join([f"• {f['item_name']} (Bought {f['n']} times)" for f in freq])

    if "milk" in q or "rice" in q or "have" in q:
        keyword = q.replace("do i have", "").replace("?", "").strip()
        rows = conn.execute("SELECT name, quantity FROM items WHERE LOWER(name) LIKE ?", (f"%{keyword}%",)).fetchall()
        conn.close()
        if not rows: return f"I couldn't find any item matching '{keyword}'."
        return "Found in your inventory:\n" + "\n".join([f"• {r['name']}: {r['quantity']} in stock" for r in rows])

    if "how many" in q or "total" in q:
        rows = conn.execute("SELECT COUNT(*) as c FROM items").fetchone()
        conn.close()
        return f"You have {rows['c']} total products in stock."

    if "low" in q or "running out" in q:
        rows = conn.execute("SELECT name, quantity FROM items WHERE quantity <= 1").fetchall()
        conn.close()
        if not rows: return "You have sufficient stock for all items."
        return "Items running low:\n" + "\n".join([f"• {r['name']}: Only {r['quantity']} left" for r in rows])

    conn.close()
    return "I didn't understand that. Try asking: 'how many products?', 'what is expiring?', 'how much did I spend?', or 'do I have milk?'"