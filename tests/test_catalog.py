import pytest
from pydantic import ValidationError
from app.config import settings, BASE_DIR
from app.database import (
    init_db,
    insert_product,
    get_product,
    list_products,
    DuplicateProductError,
)
from app.schemas import Product


@pytest.fixture(autouse=True)
def setup_test_db(monkeypatch):
    """Override database configuration to use a temporary SQLite file for testing."""
    test_db_file = BASE_DIR / "data" / "test_gateway.db"
    
    # Clean up any leftover test database from a crashed run
    if test_db_file.exists():
        try:
            test_db_file.unlink()
        except OSError:
            pass

    monkeypatch.setattr(settings, "database_url", "sqlite:///./data/test_gateway.db")
    init_db()

    yield

    # Clean up test database after the test runs
    if test_db_file.exists():
        try:
            test_db_file.unlink()
        except OSError:
            pass



def test_valid_product_creation():
    """Verify validation passes for valid product fields."""
    product = Product(
        product_id="PROD-123",
        name="Logitech Mouse",
        description="Wireless office mouse",
        price=1200.50,
        category="accessories",
        stock=10,
        image_url="https://example.com/mouse.jpg",
    )
    assert product.product_id == "PROD-123"
    assert product.name == "Logitech Mouse"
    assert product.price == 1200.50
    assert product.stock == 10


def test_invalid_price():
    """Verify validation fails for price <= 0."""
    with pytest.raises(ValidationError):
        Product(
            product_id="PROD-123",
            name="Logitech Mouse",
            price=0,  # Invalid
            category="accessories",
            stock=10,
        )

    with pytest.raises(ValidationError):
        Product(
            product_id="PROD-123",
            name="Logitech Mouse",
            price=-5.5,  # Invalid
            category="accessories",
            stock=10,
        )


def test_invalid_stock():
    """Verify validation fails for stock < 0."""
    with pytest.raises(ValidationError):
        Product(
            product_id="PROD-123",
            name="Logitech Mouse",
            price=1200.50,
            category="accessories",
            stock=-1,  # Invalid
        )


def test_invalid_empty_fields():
    """Verify validation fails for empty product_id, name, or category."""
    with pytest.raises(ValidationError):
        Product(product_id="", name="Mouse", price=100.0, category="electronics", stock=5)

    with pytest.raises(ValidationError):
        Product(product_id="P-01", name="", price=100.0, category="electronics", stock=5)

    with pytest.raises(ValidationError):
        Product(product_id="P-01", name="Mouse", price=100.0, category="", stock=5)


def test_database_insert_and_retrieve():
    """Verify inserting and retrieving a valid product from the database."""
    product = Product(
        product_id="PROD-123",
        name="Logitech Mouse",
        description="Wireless office mouse",
        price=1200.50,
        category="accessories",
        stock=10,
        image_url="https://example.com/mouse.jpg",
    )

    # Insert
    insert_product(product)

    # Retrieve by ID
    retrieved = get_product("PROD-123")
    assert retrieved is not None
    assert retrieved.product_id == "PROD-123"
    assert retrieved.name == "Logitech Mouse"
    assert retrieved.price == 1200.50
    assert retrieved.stock == 10
    assert retrieved.image_url == "https://example.com/mouse.jpg"

    # List all
    all_products = list_products()
    assert len(all_products) == 1
    assert all_products[0].product_id == "PROD-123"


def test_duplicate_product_id():
    """Verify inserting a duplicate product_id raises DuplicateProductError."""
    p1 = Product(
        product_id="PROD-123",
        name="Logitech Mouse",
        price=1200.50,
        category="accessories",
        stock=10,
    )
    p2 = Product(
        product_id="PROD-123",  # Duplicate ID
        name="Keychron Keyboard",
        price=4500.0,
        category="electronics",
        stock=5,
    )

    insert_product(p1)
    with pytest.raises(DuplicateProductError):
        insert_product(p2)
