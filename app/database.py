import sqlite3
from pathlib import Path
from typing import List, Optional
from app.config import settings, BASE_DIR
from app.schemas import Product, Cart, CartItem, Order, OrderItem


class DuplicateProductError(Exception):
    """Exception raised when attempting to insert a product with an existing ID."""
    pass


def get_db_path() -> str:
    """Extract SQLite database file path from database URL."""
    db_url = settings.database_url
    if db_url.startswith("sqlite:///"):
        rel_or_abs_path = db_url.replace("sqlite:///", "")
        if rel_or_abs_path == ":memory:":
            return ":memory:"
        # Resolve relative paths against project root
        return str((BASE_DIR / rel_or_abs_path).resolve())
    return db_url


def get_db_connection() -> sqlite3.Connection:
    """Create and return a configured SQLite connection."""
    db_path = get_db_path()
    if db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create products table and verify connectivity."""
    conn = get_db_connection()
    try:
        # Enable WAL mode and foreign keys for SQLite performance & integrity
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        
        # Create products table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS products (
                product_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                price REAL NOT NULL,
                category TEXT NOT NULL,
                stock INTEGER NOT NULL,
                image_url TEXT
            );
        """)
        
        # Create carts table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS carts (
                cart_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)
        
        # Create order_items table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cart_items (
                cart_id TEXT NOT NULL,
                product_id TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                unit_price REAL NOT NULL,
                PRIMARY KEY (cart_id, product_id),
                FOREIGN KEY (cart_id) REFERENCES carts (cart_id),
                FOREIGN KEY (product_id) REFERENCES products (product_id)
            );
        """)
        
        # Create orders table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                cart_id TEXT NOT NULL,
                total_amount REAL NOT NULL,
                currency TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                payment_provider TEXT,
                razorpay_order_id TEXT,
                payment_status TEXT,
                FOREIGN KEY (cart_id) REFERENCES carts (cart_id)
            );
        """)
        
        # Create order_items table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS order_items (
                order_id TEXT NOT NULL,
                product_id TEXT NOT NULL,
                product_name TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                unit_price REAL NOT NULL,
                PRIMARY KEY (order_id, product_id),
                FOREIGN KEY (order_id) REFERENCES orders (order_id),
                FOREIGN KEY (product_id) REFERENCES products (product_id)
            );
        """)
        # Create audit_logs table — append-only, never updated by normal logging
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT    NOT NULL,
                actor     TEXT    NOT NULL,
                action    TEXT    NOT NULL,
                arguments TEXT,
                result    TEXT,
                policy_decision TEXT,
                reason    TEXT,
                success   INTEGER NOT NULL DEFAULT 1,
                error_code TEXT
            );
        """)

        # Schema migrations for existing databases
        for col in ["payment_provider", "razorpay_order_id", "payment_status"]:
            try:
                conn.execute(f"ALTER TABLE orders ADD COLUMN {col} TEXT;")
            except sqlite3.OperationalError:
                # Column already exists
                pass

        conn.commit()

    finally:
        conn.close()


def insert_product(product: Product) -> None:
    """Insert a product into SQLite database. Raises DuplicateProductError on duplicate ID."""
    conn = get_db_connection()
    try:
        conn.execute(
            """
            INSERT INTO products (product_id, name, description, price, category, stock, image_url)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                product.product_id,
                product.name,
                product.description,
                product.price,
                product.category,
                product.stock,
                product.image_url,
            ),
        )
        conn.commit()
    except sqlite3.IntegrityError as exc:
        if "UNIQUE constraint failed: products.product_id" in str(exc) or "UNIQUE constraint failed" in str(exc):
            raise DuplicateProductError(f"Product with ID '{product.product_id}' already exists.")
        raise exc
    finally:
        conn.close()


def get_product(product_id: str) -> Optional[Product]:
    """Retrieve a product by product_id."""
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT product_id, name, description, price, category, stock, image_url FROM products WHERE product_id = ?",
            (product_id,),
        ).fetchone()
        if row:
            return Product(**dict(row))
        return None
    finally:
        conn.close()


def list_products() -> List[Product]:
    """Retrieve all products from the database."""
    conn = get_db_connection()
    try:
        rows = conn.execute(
            "SELECT product_id, name, description, price, category, stock, image_url FROM products"
        ).fetchall()
        return [Product(**dict(row)) for row in rows]
    finally:
        conn.close()


def search_products(
    query: Optional[str] = None,
    category: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    in_stock_only: bool = True,
) -> List[Product]:
    """Search products using multiple filters."""
    conn = get_db_connection()
    try:
        sql = "SELECT product_id, name, description, price, category, stock, image_url FROM products WHERE 1=1"
        params = []
        
        if in_stock_only:
            sql += " AND stock > 0"
            
        if query:
            # Split the query into individual words so that "wireless mouse"
            # matches a product whose name contains "Wireless" AND/OR "mouse"
            # separately. Each word is searched case-insensitively.
            words = [w.strip() for w in query.split() if w.strip()]
            if words:
                word_clauses = []
                for word in words:
                    word_clauses.append(
                        "(lower(name) LIKE lower(?) OR lower(description) LIKE lower(?))"
                    )
                    like_w = f"%{word}%"
                    params.extend([like_w, like_w])
                # At least one word must match
                sql += " AND (" + " OR ".join(word_clauses) + ")"
            
        if category:
            sql += " AND category = ?"
            params.append(category)
            
        if min_price is not None:
            sql += " AND price >= ?"
            params.append(min_price)
            
        if max_price is not None:
            sql += " AND price <= ?"
            params.append(max_price)
            
        rows = conn.execute(sql, params).fetchall()
        return [Product(**dict(row)) for row in rows]
    finally:
        conn.close()



def insert_products_bulk(products: List[Product]) -> None:
    """Insert multiple products in a single transaction. Rolls back on error."""
    conn = get_db_connection()
    try:
        # conn.execute automatically starts a transaction in sqlite3 before DML
        # but we can explicitly begin
        conn.execute("BEGIN TRANSACTION;")
        for product in products:
            conn.execute(
                """
                INSERT INTO products (product_id, name, description, price, category, stock, image_url)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    product.product_id,
                    product.name,
                    product.description,
                    product.price,
                    product.category,
                    product.stock,
                    product.image_url,
                ),
            )
        conn.commit()
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        if "UNIQUE constraint failed: products.product_id" in str(exc) or "UNIQUE constraint failed" in str(exc):
            raise DuplicateProductError("A product in the batch has a duplicate ID.")
        raise exc
    except Exception as exc:
        conn.rollback()
        raise exc
    finally:
        conn.close()


def insert_cart(cart: Cart) -> None:
    """Insert a new cart into the database."""
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO carts (cart_id, status, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (cart.cart_id, cart.status, cart.created_at, cart.updated_at)
        )
        conn.commit()
    finally:
        conn.close()


def fetch_cart(cart_id: str) -> Optional[Cart]:
    """Fetch a cart by cart_id from the database."""
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT cart_id, status, created_at, updated_at FROM carts WHERE cart_id = ?",
            (cart_id,)
        ).fetchone()
        
        if not row:
            return None
            
        cart = Cart(**dict(row))
        
        items_rows = conn.execute(
            """
            SELECT ci.product_id, ci.quantity, ci.unit_price, p.name AS product_name
            FROM cart_items ci
            LEFT JOIN products p ON ci.product_id = p.product_id
            WHERE ci.cart_id = ?
            """,
            (cart_id,)
        ).fetchall()
        
        cart.items = [CartItem(**dict(item_row)) for item_row in items_rows]
        cart.subtotal = sum(item.quantity * item.unit_price for item in cart.items)
        cart.total_quantity = sum(item.quantity for item in cart.items)
        return cart
    finally:
        conn.close()


def upsert_cart_item(cart_id: str, item: CartItem) -> None:
    """Insert or update a cart item."""
    conn = get_db_connection()
    try:
        conn.execute(
            """
            INSERT INTO cart_items (cart_id, product_id, quantity, unit_price)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(cart_id, product_id) DO UPDATE SET
                quantity = excluded.quantity,
                unit_price = excluded.unit_price
            """,
            (cart_id, item.product_id, item.quantity, item.unit_price)
        )
        conn.commit()
    finally:
        conn.close()


def update_cart_timestamp(cart_id: str, updated_at: str) -> None:
    """Update the updated_at timestamp of a cart."""
    conn = get_db_connection()
    try:
        conn.execute(
            "UPDATE carts SET updated_at = ? WHERE cart_id = ?",
            (updated_at, cart_id)
        )
        conn.commit()
    finally:
        conn.close()


def upsert_cart_item_transaction(cart_id: str, item: CartItem, updated_at: str) -> None:
    """Insert or update a cart item and update the cart timestamp in a single transaction."""
    conn = get_db_connection()
    try:
        conn.execute("BEGIN TRANSACTION;")
        conn.execute(
            """
            INSERT INTO cart_items (cart_id, product_id, quantity, unit_price)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(cart_id, product_id) DO UPDATE SET
                quantity = excluded.quantity,
                unit_price = excluded.unit_price
            """,
            (cart_id, item.product_id, item.quantity, item.unit_price)
        )
        conn.execute(
            "UPDATE carts SET updated_at = ? WHERE cart_id = ?",
            (updated_at, cart_id)
        )
        conn.commit()
    except Exception as exc:
        conn.rollback()
        raise exc
    finally:
        conn.close()


def delete_cart_item_transaction(cart_id: str, product_id: str, updated_at: str) -> int:
    """Delete a cart item and update the cart timestamp in a single transaction."""
    conn = get_db_connection()
    try:
        conn.execute("BEGIN TRANSACTION;")
        cursor = conn.execute(
            "DELETE FROM cart_items WHERE cart_id = ? AND product_id = ?",
            (cart_id, product_id)
        )
        deleted_count = cursor.rowcount
        if deleted_count > 0:
            conn.execute(
                "UPDATE carts SET updated_at = ? WHERE cart_id = ?",
                (updated_at, cart_id)
            )
        conn.commit()
        return deleted_count
    except Exception as exc:
        conn.rollback()
        raise exc
    finally:
        conn.close()


def fetch_order(order_id: str) -> Optional[Order]:
    """Fetch an order by order_id."""
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT order_id, cart_id, total_amount, currency, status, created_at, payment_provider, razorpay_order_id, payment_status FROM orders WHERE order_id = ?",
            (order_id,)
        ).fetchone()
        
        if not row:
            return None
            
        order = Order(**dict(row))
        
        items_rows = conn.execute(
            "SELECT order_id, product_id, product_name, quantity, unit_price FROM order_items WHERE order_id = ?",
            (order_id,)
        ).fetchall()
        
        order.items = [OrderItem(**dict(item_row)) for item_row in items_rows]
        return order
    finally:
        conn.close()


def create_order_transaction(order: Order, items: List[OrderItem]) -> None:
    """Create order and order items, and update cart status in a single transaction."""
    conn = get_db_connection()
    try:
        conn.execute("BEGIN TRANSACTION;")
        
        # Update cart status, ensuring it's ACTIVE
        cursor = conn.execute(
            "UPDATE carts SET status = 'CHECKOUT' WHERE cart_id = ? AND status = 'ACTIVE'",
            (order.cart_id,)
        )
        if cursor.rowcount == 0:
            raise ValueError(f"Cart '{order.cart_id}' is not ACTIVE or does not exist.")
            
        # Insert order
        conn.execute(
            "INSERT INTO orders (order_id, cart_id, total_amount, currency, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (order.order_id, order.cart_id, order.total_amount, order.currency, order.status, order.created_at)
        )
        
        # Insert order items
        for item in items:
            conn.execute(
                """
                INSERT INTO order_items (order_id, product_id, product_name, quantity, unit_price)
                VALUES (?, ?, ?, ?, ?)
                """,
                (item.order_id, item.product_id, item.product_name, item.quantity, item.unit_price)
            )
            
        conn.commit()
    except Exception as exc:
        conn.rollback()
        raise exc
    finally:
        conn.close()


def update_payment_details(order_id: str, provider: str, razorpay_order_id: str, payment_status: str) -> None:
    """Update payment metadata for an existing order."""
    conn = get_db_connection()
    try:
        conn.execute(
            "UPDATE orders SET payment_provider = ?, razorpay_order_id = ?, payment_status = ? WHERE order_id = ?",
            (provider, razorpay_order_id, payment_status, order_id)
        )
        conn.commit()
    finally:
        conn.close()


def update_order_payment_status(order_id: str, provider: str, razorpay_order_id: str, payment_status: str) -> None:
    """Update payment information on an order."""
    conn = get_db_connection()
    try:
        conn.execute(
            """
            UPDATE orders 
            SET payment_provider = ?,
                razorpay_order_id = ?,
                payment_status = ?
            WHERE order_id = ?
            """,
            (provider, razorpay_order_id, payment_status, order_id)
        )
        conn.commit()
    finally:
        conn.close()

def list_carts(limit: int = 50) -> List[Cart]:
    """Retrieve recent carts."""
    conn = get_db_connection()
    try:
        rows = conn.execute(
            "SELECT cart_id, status, created_at, updated_at FROM carts ORDER BY created_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        carts = []
        for row in rows:
            cart = Cart(**dict(row))
            items_rows = conn.execute(
                """
                SELECT ci.product_id, ci.quantity, ci.unit_price, p.name AS product_name
                FROM cart_items ci
                LEFT JOIN products p ON ci.product_id = p.product_id
                WHERE ci.cart_id = ?
                """,
                (cart.cart_id,)
            ).fetchall()
            cart.items = [CartItem(**dict(item_row)) for item_row in items_rows]
            cart.subtotal = sum(item.quantity * item.unit_price for item in cart.items)
            cart.total_quantity = sum(item.quantity for item in cart.items)
            carts.append(cart)
        return carts
    finally:
        conn.close()

def list_orders(limit: int = 50) -> List[Order]:
    """Retrieve recent orders."""
    conn = get_db_connection()
    try:
        rows = conn.execute(
            "SELECT order_id, cart_id, total_amount, currency, status, created_at, payment_provider, razorpay_order_id, payment_status FROM orders ORDER BY created_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        orders = []
        for row in rows:
            order = Order(**dict(row))
            items_rows = conn.execute(
                "SELECT order_id, product_id, product_name, quantity, unit_price FROM order_items WHERE order_id = ?",
                (order.order_id,)
            ).fetchall()
            order.items = [OrderItem(**dict(item_row)) for item_row in items_rows]
            orders.append(order)
        return orders
    finally:
        conn.close()


def fetch_order_by_razorpay_order_id(razorpay_order_id: str) -> Optional[Order]:
    """Fetch an order by its Razorpay order ID."""
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT order_id, cart_id, total_amount, currency, status, created_at, payment_provider, razorpay_order_id, payment_status FROM orders WHERE razorpay_order_id = ?",
            (razorpay_order_id,)
        ).fetchone()
        
        if not row:
            return None
            
        order = Order(**dict(row))
        
        items_rows = conn.execute(
            "SELECT order_id, product_id, product_name, quantity, unit_price FROM order_items WHERE order_id = ?",
            (order.order_id,)
        ).fetchall()
        
        order.items = [OrderItem(**dict(item_row)) for item_row in items_rows]
        return order
    finally:
        conn.close()


