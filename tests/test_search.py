import pytest
from app.config import settings, BASE_DIR
from app.database import init_db, insert_products_bulk, search_products, get_product
from app.schemas import Product

@pytest.fixture(autouse=True)
def setup_test_db(monkeypatch):
    """Override database configuration to use a temporary SQLite file for testing."""
    test_db_file = BASE_DIR / "data" / "test_search.db"
    
    if test_db_file.exists():
        try:
            test_db_file.unlink()
        except OSError:
            pass

    monkeypatch.setattr(settings, "database_url", "sqlite:///./data/test_search.db")
    init_db()

    # Pre-populate sample catalog
    sample_products = [
        Product(product_id="M001", name="Logitech M331", description="Wireless silent mouse", price=1299.0, category="mouse", stock=12),
        Product(product_id="M002", name="Redragon K617", description="60 percent mechanical keyboard", price=2499.0, category="keyboard", stock=8),
        Product(product_id="M003", name="HyperX Cloud Stinger", description="Wireless gaming headset", price=3999.0, category="headset", stock=0), # Out of stock
        Product(product_id="M004", name="Redgear A20", description="RGB gaming mouse", price=899.0, category="mouse", stock=20),
    ]
    insert_products_bulk(sample_products)

    yield

    if test_db_file.exists():
        try:
            test_db_file.unlink()
        except OSError:
            pass


def test_text_search():
    results = search_products(query="gaming")
    assert len(results) == 1 # Only M004 is gaming AND in stock (M003 is out of stock)
    assert results[0].product_id == "M004"
    
    # Test text search ignoring case and finding description
    results2 = search_products(query="silent")
    assert len(results2) == 1
    assert results2[0].product_id == "M001"


def test_category_filtering():
    results = search_products(category="mouse")
    assert len(results) == 2
    ids = {p.product_id for p in results}
    assert ids == {"M001", "M004"}


def test_min_price():
    results = search_products(min_price=2000)
    assert len(results) == 1
    assert results[0].product_id == "M002" # M003 is out of stock


def test_max_price():
    results = search_products(max_price=1000)
    assert len(results) == 1
    assert results[0].product_id == "M004"


def test_combining_filters():
    results = search_products(category="mouse", max_price=1000)
    assert len(results) == 1
    assert results[0].product_id == "M004"


def test_out_of_stock_filtering():
    # By default, in_stock_only=True
    results = search_products(query="HyperX")
    assert len(results) == 0

    # With in_stock_only=False
    results_all = search_products(query="HyperX", in_stock_only=False)
    assert len(results_all) == 1
    assert results_all[0].product_id == "M003"


def test_exact_product_lookup():
    product = get_product("M002")
    assert product is not None
    assert product.name == "Redragon K617"


def test_nonexistent_product():
    product = get_product("INVALID_ID")
    assert product is None
