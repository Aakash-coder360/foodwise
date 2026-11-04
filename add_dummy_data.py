from core.database import init_db, get_conn
from datetime import datetime, timedelta

def generate_fake_data():
    init_db()  # Ensure tables exist
    conn = get_conn()
    c = conn.cursor()
    
    # Clear existing data
    c.execute("DELETE FROM items")
    c.execute("DELETE FROM purchases")
    
    today = datetime.now()
    today_str = today.strftime("%Y-%m-%d")
    
    # Helper function for dates
    def get_date(days):
        return (today + timedelta(days=days)).strftime("%Y-%m-%d")
    
    # Pure Grocery Items (NO VEGETABLES)
    items = [
        # Perishable (Expiring/Expired)
        ("Milk", "Dairy", 2, "L", 60.0, get_date(3), today_str),       # Expiring in 3 days
        ("Curd", "Dairy", 1, "kg", 80.0, get_date(-1), today_str),     # Expired yesterday
        ("Paneer", "Dairy", 0.5, "kg", 150.0, get_date(2), today_str), # Expiring in 2 days
        ("Bread", "Bakery", 1, "pack", 40.0, get_date(2), today_str),  # Expiring in 2 days
        
        # Non-Perishable (No expiry - Staples)
        ("Rice (Basmati)", "Grain", 10, "kg", 120.0, None, today_str),
        ("Wheat Flour (Atta)", "Grain", 5, "kg", 55.0, None, today_str),
        ("Sugar", "Grain", 2, "kg", 45.0, None, today_str),
        ("Toor Dal", "Grain", 1, "kg", 160.0, get_date(30), today_str), # Dal expires in a month
        ("Cooking Oil", "Other", 1, "L", 140.0, None, today_str),
        ("Salt", "Other", 0.5, "kg", 20.0, None, today_str),
        
        # Beverages & Snacks
        ("Tea Powder", "Beverage", 1, "pack", 130.0, None, today_str),
        ("Coffee", "Beverage", 1, "pack", 250.0, None, today_str),
        ("Biscuits", "Snack", 2, "pack", 30.0, get_date(60), today_str),
        ("Namkeen", "Snack", 1, "pack", 50.0, get_date(45), today_str),
        ("Maggi Noodles", "Snack", 4, "pack", 15.0, get_date(90), today_str)
    ]
    
    c.executemany("""
        INSERT INTO items (name, category, quantity, unit, price, expiry_date, added_date) 
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, items)
    
    # 10 Dummy Purchases (For monthly report and frequent items)
    purchases = [
        ("Milk", "Dairy", 2, 60.0, today_str),
        ("Bread", "Bakery", 1, 40.0, today_str),
        ("Rice (Basmati)", "Grain", 10, 120.0, today_str),
        ("Wheat Flour (Atta)", "Grain", 5, 55.0, today_str),
        ("Maggi Noodles", "Snack", 4, 15.0, today_str),
        ("Milk", "Dairy", 1, 60.0, get_date(-2)),   # Past purchase
        ("Tea Powder", "Beverage", 1, 130.0, get_date(-3)),
        ("Biscuits", "Snack", 2, 30.0, get_date(-4)),
        ("Milk", "Dairy", 2, 60.0, get_date(-5)),   # Milk is bought most often
        ("Cooking Oil", "Other", 1, 140.0, get_date(-7))
    ]
    
    c.executemany("""
        INSERT INTO purchases (item_name, category, quantity, price, purchase_date) 
        VALUES (?, ?, ?, ?, ?)
    """, purchases)
    
    conn.commit()
    conn.close()
    print("✅ 15 Pure Grocery Items (No Vegetables) and 10 Purchases added successfully!")
    print("🔄 Refresh your dashboard to see the updated list.")

if __name__ == "__main__":
    generate_fake_data()