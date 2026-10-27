import sys
from core.database import init_db, get_conn, export_to_csv, get_monthly_report, get_frequent_items
from core.utils import is_valid_date, is_valid_name, generate_chart_base64
from core.ai import ask_gemini, ask_offline
import base64
import os

try:
    from colorama import init as cinit, Fore, Style
    cinit(autoreset=True)
except ImportError:
    class Fore: RED=GREEN=YELLOW=CYAN=RESET=""
    class Style: BRIGHT=RESET_ALL=""

def render_menu():
    print(Fore.CYAN + Style.BRIGHT + "=" * 50)
    print("     🍎  FOODWISE CLI - Pro Edition")
    print("=" * 50 + Style.RESET_ALL)
    print("1. Add Item          2. Record Purchase")
    print("3. View All Items    4. Search Items")
    print("5. Monthly Report    6. Generate Chart")
    print("7. Ask AI            8. Export CSV")
    print("0. Exit")
    print("-" * 50)

def add_item():
    print(Fore.YELLOW + "\n--- Add Item ---" + Fore.RESET)
    name = input("Name: ").strip()
    if not is_valid_name(name): return print(Fore.RED + "Invalid name." + Fore.RESET)
    category = input("Category: ").strip()
    try:
        qty = float(input("Quantity: "))
        price = float(input("Price: "))
    except ValueError: return print(Fore.RED + "Numbers only." + Fore.RESET)
    expiry = input("Expiry (YYYY-MM-DD) or Enter: ").strip() or None
    if expiry and not is_valid_date(expiry): return print(Fore.RED + "Invalid date." + Fore.RESET)

    conn = get_conn()
    conn.execute("INSERT INTO items (name, category, quantity, unit, price, expiry_date, added_date) VALUES (?, ?, ?, ?, ?, ?, ?)", (name, category, qty, "pcs", price, expiry, "2026-10-26"))
    conn.commit(); conn.close()
    print(Fore.GREEN + f"✅ Added {name}." + Fore.RESET)

def record_purchase():
    print(Fore.YELLOW + "\n--- Record Purchase ---" + Fore.RESET)
    name = input("Item name: ").strip()
    try:
        qty = float(input("Quantity: "))
        price = float(input("Price: "))
    except ValueError: return print(Fore.RED + "Numbers only." + Fore.RESET)
    conn = get_conn()
    conn.execute("INSERT INTO purchases (item_name, category, quantity, price, purchase_date) VALUES (?, ?, ?, ?, ?)", (name, "Other", qty, price, "2026-10-26"))
    conn.commit(); conn.close()
    print(Fore.GREEN + f"✅ Recorded purchase." + Fore.RESET)

def view_items():
    print(Fore.YELLOW + "\n--- All Items ---" + Fore.RESET)
    conn = get_conn()
    items = conn.execute("SELECT * FROM items").fetchall()
    conn.close()
    if not items: return print("No items.")
    for i in items:
        print(f"{i['id']:<3} {i['name']:<15} {i['category']:<12} {i['quantity']:<5} ₹{i['price']:<5} {i['expiry_date'] or '—'}")

def search_items():
    q = input("Search name: ").strip()
    conn = get_conn()
    items = conn.execute("SELECT * FROM items WHERE LOWER(name) LIKE ?", (f"%{q.lower()}%",)).fetchall()
    conn.close()
    if not items: return print("Not found.")
    for i in items: print(f"{i['name']} ({i['quantity']})")

def monthly_report():
    rep = get_monthly_report()
    print(Fore.CYAN + f"\n📈 Total Spend: ₹{rep['total']}" + Fore.RESET)
    for c in rep['by_cat']: print(f"  {c['category']}: ₹{c['s']}")

def generate_chart():
    chart_b64 = generate_chart_base64()
    if not chart_b64: return print("No data.")
    with open("chart.png", "wb") as f:
        f.write(base64.b64decode(chart_b64))
    print(Fore.GREEN + "✅ Chart saved as chart.png" + Fore.RESET)

def ask_ai():
    q = input("Your question: ").strip()
    if not q: return
    ans, err = ask_gemini(q)
    if err: print(Fore.CYAN + f"[Offline] {ask_offline(q)}" + Fore.RESET)
    else: print(Fore.GREEN + f"[Online] {ans}" + Fore.RESET)

def main():
    init_db()
    while True:
        render_menu()
        choice = input("Choose: ").strip()
        if choice == "1": add_item()
        elif choice == "2": record_purchase()
        elif choice == "3": view_items()
        elif choice == "4": search_items()
        elif choice == "5": monthly_report()
        elif choice == "6": generate_chart()
        elif choice == "7": ask_ai()
        elif choice == "8": print(Fore.GREEN + f"✅ Exported to {export_to_csv()}" + Fore.RESET)
        elif choice == "0": break
        else: print("Invalid.")
        input("\nPress Enter...")

if __name__ == "__main__":
    main()