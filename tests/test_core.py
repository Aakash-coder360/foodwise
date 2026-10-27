import pytest
from core.database import init_db, get_conn, export_to_csv
from core.utils import is_valid_date, is_valid_name, expiry_status
import os

def test_database_init():
    init_db()
    assert os.path.exists("foodwise.db")

def test_date_validation():
    assert is_valid_date("2026-12-31") is True
    assert is_valid_date("31-12-2026") is False

def test_name_validation():
    assert is_valid_name("Milk") is True
    assert is_valid_name("Milk@#") is False

def test_expiry_status():
    label, color = expiry_status("2020-01-01")
    assert "EXPIRED" in label
    assert color == "red"

def test_csv_export():
    init_db()
    filename = export_to_csv("test_report.csv")
    assert os.path.exists(filename)
    os.remove(filename)