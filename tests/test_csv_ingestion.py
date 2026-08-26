import os
import csv
from pathlib import Path
import pytest
from app.config import settings, BASE_DIR
from app.database import init_db, list_products
from app.catalog import import_products_from_csv

@pytest.fixture(autouse=True)
def setup_test_db(monkeypatch):
    """Override database configuration to use a temporary SQLite file for testing."""
    test_db_file = BASE_DIR / "data" / "test_gateway.db"
    
    if test_db_file.exists():
        try:
            test_db_file.unlink()
        except OSError:
            pass

    monkeypatch.setattr(settings, "database_url", "sqlite:///./data/test_gateway.db")
    init_db()

    yield

    if test_db_file.exists():
        try:
            test_db_file.unlink()
        except OSError:
            pass

@pytest.fixture
def temp_csv(tmp_path):
    """Fixture to provide a path for a temporary CSV file."""
    def _create_csv(data, filename="test_catalog.csv"):
        file_path = tmp_path / filename
        with open(file_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerows(data)
        return str(file_path)
    return _create_csv

def test_successful_import():
    # Use the sample CSV created in the data directory
    csv_path = str(BASE_DIR / "data" / "products.csv")
    summary = import_products_from_csv(csv_path)
    
    assert summary["validation_errors"] == []
    assert summary["rejected_rows"] == 0
    assert summary["imported_rows"] == 4
    
    products = list_products()
    assert len(products) == 4
    names = [p.name for p in products]
    assert "Logitech M331" in names
    assert "Redragon K617" in names

def test_invalid_price(temp_csv):
    data = [
        ["product_id", "name", "description", "price", "category", "stock", "image_url"],
        ["M001", "Mouse", "", "-10", "electronics", "5", ""] # Invalid price
    ]
    csv_path = temp_csv(data)
    summary = import_products_from_csv(csv_path)
    
    assert summary["rejected_rows"] == 1
    assert any("price" in err for err in summary["validation_errors"])
    assert len(list_products()) == 0 # Transaction should rollback/not insert

def test_invalid_stock(temp_csv):
    data = [
        ["product_id", "name", "description", "price", "category", "stock", "image_url"],
        ["M001", "Mouse", "", "10", "electronics", "-5", ""] # Invalid stock
    ]
    csv_path = temp_csv(data)
    summary = import_products_from_csv(csv_path)
    
    assert summary["rejected_rows"] == 1
    assert any("stock" in err for err in summary["validation_errors"])
    assert len(list_products()) == 0

def test_missing_required_column(temp_csv):
    # Missing 'price' column
    data = [
        ["product_id", "name", "description", "category", "stock", "image_url"],
        ["M001", "Mouse", "", "electronics", "5", ""]
    ]
    csv_path = temp_csv(data)
    summary = import_products_from_csv(csv_path)
    
    assert len(summary["validation_errors"]) > 0
    assert "Missing required columns: price" in summary["validation_errors"][0]
    assert len(list_products()) == 0

def test_duplicate_product_id_in_csv(temp_csv):
    data = [
        ["product_id", "name", "description", "price", "category", "stock", "image_url"],
        ["M001", "Mouse 1", "", "10", "electronics", "5", ""],
        ["M001", "Mouse 2", "", "15", "electronics", "2", ""] # Duplicate ID
    ]
    csv_path = temp_csv(data)
    summary = import_products_from_csv(csv_path)
    
    assert summary["rejected_rows"] == 1
    assert any("Duplicate product_id" in err for err in summary["validation_errors"])
    assert len(list_products()) == 0

def test_transaction_rollback_when_import_fails(temp_csv):
    # One valid, one invalid. The valid one should NOT be inserted.
    data = [
        ["product_id", "name", "description", "price", "category", "stock", "image_url"],
        ["M001", "Valid Mouse", "", "10", "electronics", "5", ""],
        ["M002", "Invalid Mouse", "", "-10", "electronics", "5", ""]
    ]
    csv_path = temp_csv(data)
    summary = import_products_from_csv(csv_path)
    
    assert summary["rejected_rows"] == 1
    assert summary["imported_rows"] == 0
    assert len(list_products()) == 0
