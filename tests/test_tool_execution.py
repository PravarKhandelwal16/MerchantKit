import pytest
from app.config import settings, BASE_DIR
from app.database import init_db, insert_products_bulk
from app.schemas import Product
from app.executor import execute_tool, TOOL_HANDLERS

@pytest.fixture(autouse=True)
def setup_test_db(monkeypatch):
    """Override database configuration to use a temporary SQLite file for testing."""
    test_db_file = BASE_DIR / "data" / "test_executor.db"
    
    if test_db_file.exists():
        try:
            test_db_file.unlink()
        except OSError:
            pass

    monkeypatch.setattr(settings, "database_url", "sqlite:///./data/test_executor.db")
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

def test_valid_search_products_call():
    response = execute_tool("search_products", {"query": "wireless"})
    assert response["success"] is True
    assert response["tool"] == "search_products"
    assert "data" in response
    assert len(response["data"]) == 1
    assert response["data"][0].product_id == "M001"

def test_valid_get_product_call():
    response = execute_tool("get_product", {"product_id": "M002"})
    assert response["success"] is True
    assert response["tool"] == "get_product"
    assert "data" in response
    assert response["data"] is not None
    assert response["data"].name == "Redragon K617"

def test_missing_required_argument():
    response = execute_tool("get_product", {})
    assert response["success"] is False
    assert response["tool"] == "get_product"
    assert "error" in response
    assert response["error"]["code"] == "INVALID_ARGUMENTS"
    assert "product_id" in response["error"]["message"]

def test_invalid_argument_type():
    # max_price should be a number, passing a dict or list will fail Pydantic validation
    response = execute_tool("search_products", {"max_price": ["not", "a", "number"]})
    assert response["success"] is False
    assert response["tool"] == "search_products"
    assert response["error"]["code"] == "INVALID_ARGUMENTS"
    assert "max_price" in response["error"]["message"]

def test_unknown_tool():
    response = execute_tool("unknown_tool", {"some_arg": "value"})
    assert response["success"] is False
    assert response["tool"] == "unknown_tool"
    assert response["error"]["code"] == "TOOL_NOT_FOUND"

def test_malformed_arguments():
    # arguments should be a dict, passing a string
    response = execute_tool("search_products", "not_a_dict")
    assert response["success"] is False
    assert response["tool"] == "search_products"
    assert response["error"]["code"] == "MALFORMED_ARGUMENTS"

def test_empty_tool_name():
    response = execute_tool("", {})
    assert response["success"] is False
    assert response["tool"] == ""
    assert response["error"]["code"] == "MISSING_TOOL_NAME"

def test_ensuring_only_registered_tools_can_execute():
    # TOOL_HANDLERS is a hardcoded dict that maps tool names to callables
    assert len(TOOL_HANDLERS) == 10

    assert "search_products" in TOOL_HANDLERS
    assert "get_product" in TOOL_HANDLERS
