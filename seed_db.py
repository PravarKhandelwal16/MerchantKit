"""
Helper script to seed the database with products from data/products.csv.
"""
from app.database import init_db
from app.catalog import import_products_from_csv
from pathlib import Path


def main():
    print("Initializing database tables...")
    init_db()

    csv_path = Path(__file__).resolve().parent / "data" / "products.csv"
    print(f"Importing products from {csv_path}...")

    result = import_products_from_csv(str(csv_path))

    if result.get("validation_errors"):
        print("Failed to import products:")
        for err in result["validation_errors"]:
            print(f"  - {err}")
    else:
        print(f"Success! Imported {result['imported_rows']} products.")
        print(f"Total rows parsed: {result['total_rows']}")


if __name__ == "__main__":
    main()
