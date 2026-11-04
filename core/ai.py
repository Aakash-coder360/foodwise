import json
from google import genai
from .logger import logger
from .database import get_conn, get_monthly_report, get_frequent_items

CONFIG_FILE = "config.txt"
GEMINI_MODEL = "gemini-3.8-flash" 

def load_api_key():
    try:
        with open(CONFIG_FILE, "r") as f:
            for line in f:
                if "GEMINI_API_KEY" in line:
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
        prompt = f"You are FoodWise, a smart grocery assistant. Answer concisely in English. Question: {question}"
        resp = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
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
    
    # 1. Expiry check
    if "expir" in q or "khatam" in q or "spoil" in q:
        rows = conn.execute("SELECT name, expiry_date FROM items WHERE expiry_date IS NOT NULL AND date(expiry_date) <= date('now', '+7 day')").fetchall()
        conn.close()
        if not rows: return "Everything is fresh! Nothing is expiring soon."
        return "Expiring soon:\n" + "\n".join([f"• {r['name']} (Expires: {r['expiry_date']})" for r in rows])

    # 2. Spend check
    if "spend" in q or "spent" in q or "cost" in q or "budget" in q or "kharch" in q:
        rep = get_monthly_report()
        conn.close()
        return f"Total spend for this month: ₹{rep['total']}"

    # 3. Frequent items check
    if "frequent" in q or "buy most" in q or "often" in q:
        freq = get_frequent_items()
        conn.close()
        if not freq: return "No purchase history found yet."
        return "Most frequently purchased items:\n" + "\n".join([f"• {f['item_name']} (Bought {f['n']} times)" for f in freq])

    # 4. Low stock check
    if "low" in q or "running out" in q or "finish" in q:
        rows = conn.execute("SELECT name, quantity FROM items WHERE quantity <= 1").fetchall()
        conn.close()
        if not rows: return "You have sufficient stock for all items."
        return "Items running low:\n" + "\n".join([f"• {r['name']}: Only {r['quantity']} left" for r in rows])

    # 5. Total products check
    if "how many" in q or "total" in q:
        rows = conn.execute("SELECT COUNT(*) as c FROM items").fetchone()
        conn.close()
        return f"You have {rows['c']} total products in stock."

    # 6. SMART ITEM SEARCH (Powerful version)
    # Remove common words to find the item name
    ignore_words = ["what", "is", "how", "much", "do", "i", "have", "the", "of", "quantity", "price", "show", "me", "a", "an", "there", "any", "in", "stock", "is there", "tell"]
    words = q.replace("?", "").replace("'", "").split()
    search_terms = [w for w in words if w not in ignore_words]

    # Try searching with the whole remaining phrase
    if search_terms:
        phrase = " ".join(search_terms)
        item = conn.execute("SELECT name, quantity, unit, price, expiry_date FROM items WHERE LOWER(name) LIKE ?", (f"%{phrase}%",)).fetchone()
        if item:
            conn.close()
            exp_info = f" (Expires: {item['expiry_date']})" if item['expiry_date'] else ""
            return f"Found it! You have {item['quantity']} {item['unit'] or ''} of {item['name']} in stock (Price: ₹{item['price']}){exp_info}."

        # Try word by word
        for word in search_terms:
            if len(word) > 2: 
                item = conn.execute("SELECT name, quantity, unit, price, expiry_date FROM items WHERE LOWER(name) LIKE ?", (f"%{word}%",)).fetchone()
                if item:
                    conn.close()
                    exp_info = f" (Expires: {item['expiry_date']})" if item['expiry_date'] else ""
                    return f"Found it! You have {item['quantity']} {item['unit'] or ''} of {item['name']} in stock (Price: ₹{item['price']}){exp_info}."

    # 7. Fallback
    conn.close()
    return "I couldn't find that item in your inventory. Try asking: 'what is expiring?', 'how much did I spend?', or 'do I have milk?'"