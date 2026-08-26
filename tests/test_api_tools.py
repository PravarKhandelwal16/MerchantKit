import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings, BASE_DIR
from app.database import init_db, insert_products_bulk
from app.schemas import Product

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_test_db(monkeypatch):
    """Override database configuration to use a temporary SQLite file for testing."""
    test_db_file = BASE_DIR / "data" / "test_api_tools.db"
    
    if test_db_file.exists():
        try:
            test_db_file.unlink()
        except OSError:
            pass

    monkeypatch.setattr(settings, "database_url", "sqlite:///./data/test_api_tools.db")
    init_db()

    # Pre-populate sample catalog
    sample_products = [
        Product(product_id="M001", name="Logitech M331", description="Wireless silent mouse", price=1299.0, category="mouse", stock=12),
        Product(product_id="M002", name="Redragon K617", description="60 percent mechanical keyboard", price=2499.0, category="keyboard", stock=8),
    ]
    insert_products_bulk(sample_products)

    yield

    if test_db_file.exists():
        try:
            test_db_file.unlink()
        except OSError:
            pass

def test_api_valid_search_request():
    response = client.post("/tools/execute", json={
        "tool": "search_products",
        "arguments": {
            "query": "wireless"
        }
    })
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["tool"] == "search_products"
    assert len(data["data"]) == 1
    assert data["data"][0]["product_id"] == "M001"

def test_api_valid_get_product_request():
    response = client.post("/tools/execute", json={
        "tool": "get_product",
        "arguments": {
            "product_id": "M002"
        }
    })
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["tool"] == "get_product"
    assert data["data"]["name"] == "Redragon K617"

def test_api_unknown_tool():
    response = client.post("/tools/execute", json={
        "tool": "fake_tool",
        "arguments": {}
    })
    
    assert response.status_code == 404
    data = response.json()
    assert data["success"] is False
    assert data["tool"] == "fake_tool"
    assert data["error"]["code"] == "TOOL_NOT_FOUND"

def test_api_malformed_request():
    # Missing 'tool' key entirely
    response = client.post("/tools/execute", json={
        "arguments": {}
    })
    
    # FastAPI/Pydantic intercepts this before it hits the executor
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data

def test_api_invalid_arguments():
    response = client.post("/tools/execute", json={
        "tool": "get_product",
        "arguments": {} # Missing required product_id
    })
    
    assert response.status_code == 422
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "INVALID_ARGUMENTS"
