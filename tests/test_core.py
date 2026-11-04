import pytest
import os
from core.database import init_db, get_conn, export_to_csv
from core.utils import is_valid_date, is_valid_name, expiry_status
from core.ai import ask_offline

# ---------------------------------------------------------
# 1. Database Tests
# ---------------------------------------------------------
def test_database_init():
    """Test if database and tables are created."""
    init_db()
    assert os.path.exists("foodwise.db")
    
    conn = get_conn()
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    table_names = [t['name'] for t in tables]
    conn.close()
    
    assert "items" in table_names
    assert "purchases" in table_names

def test_add_item_to_db():
    """Test if an item can be added and retrieved."""
    init_db()
    conn = get_conn()
    conn.execute("DELETE FROM items") # Clean slate
    
    conn.execute("""
        INSERT INTO items (name, category, quantity, unit, price, expiry_date, added_date) 
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, ("TestMilk", "Dairy", 2, "L", 60.0, None, "2026-01-01"))
    conn.commit()
    
    item = conn.execute("SELECT * FROM items WHERE name='TestMilk'").fetchone()
    conn.close()
    
    assert item is not None
    assert item['name'] == "TestMilk"
    assert item['price'] == 60.0

# ---------------------------------------------------------
# 2. Utils & Validation Tests
# ---------------------------------------------------------
def test_date_validation():
    """Test date regex and parsing."""
    assert is_valid_date("2026-12-31") is True
    assert is_valid_date("31-12-2026") is False
    assert is_valid_date("2026/12/31") is False
    assert is_valid_date("hello") is False

def test_name_validation():
    """Test regex for item names (no special characters)."""
    assert is_valid_name("Milk") is True
    assert is_valid_name("Wheat Flour") is True
    assert is_valid_name("Milk@#") is False
    assert is_valid_name("Milk$") is False

def test_expiry_status_expired():
    """Test status for already expired items."""
    label, color = expiry_status("2020-01-01")
    assert "EXPIRED" in label
    assert color == "red"

def test_expiry_status_no_expiry():
    """Test status for non-perishable items (no expiry)."""
    label, color = expiry_status(None)
    assert "non-perishable" in label
    assert color == "gray"

# ---------------------------------------------------------
# 3. CSV Export Tests
# ---------------------------------------------------------
def test_csv_export():
    """Test if data is exported to CSV correctly."""
    init_db()
    filename = export_to_csv("test_report.csv")
    assert os.path.exists(filename)
    os.remove(filename) # Cleanup

# ---------------------------------------------------------
# 4. AI Offline Tests
# ---------------------------------------------------------
def test_offline_ai_expiry():
    """Test if offline AI correctly identifies expiry questions."""
    response = ask_offline("what is expiring?")
    # It should either say "Everything is fresh" or list items
    assert isinstance(response, str)
    assert len(response) > 0

def test_offline_ai_spend():
    """Test if offline AI answers spend questions."""
    response = ask_offline("how much did I spend?")
    assert "Total spend" in response

def test_offline_ai_unknown():
    """Test fallback response for unknown questions."""
    response = ask_offline("xyz abc random nonsense")
    assert "I didn't understand that" in response