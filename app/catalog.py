import csv
from typing import Dict, Any, List
from pydantic import ValidationError
from app.schemas import Product
from app.database import insert_products_bulk, DuplicateProductError


def import_products_from_csv(file_path: str) -> Dict[str, Any]:
    """
    Reads a CSV file, validates rows against the Product schema,
    and bulk inserts them into the database in a transaction.
    """
    required_columns = {"product_id", "name", "price", "category", "stock"}
    
    summary = {
        "total_rows": 0,
        "imported_rows": 0,
        "rejected_rows": 0,
        "validation_errors": []
    }

    try:
        with open(file_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            
            if reader.fieldnames is None:
                summary["validation_errors"].append("CSV file is empty or missing headers.")
                return summary
                
            headers = set(reader.fieldnames)
            missing_cols = required_columns - headers
            if missing_cols:
                summary["validation_errors"].append(f"Missing required columns: {', '.join(missing_cols)}")
                return summary

            products_to_insert: List[Product] = []
            seen_ids = set()

            for row_num, row in enumerate(reader, start=2): # Start at 2 because row 1 is header
                summary["total_rows"] += 1
                
                try:
                    # DictReader returns strings for everything. Pydantic can handle coercion.
                    # We pass the row directly. Empty strings for numeric fields will fail validation, which is correct.
                    # For optional string fields, empty string is valid.
                    # If we explicitly want None for empty strings, we can clean only specific fields, but passing row is generally safer.
                    
                    # Convert empty strings to None only for fields where empty string is clearly invalid or None is preferred,
                    # but actually Pydantic 2 handles empty strings for Optionals if we use model_validate or just pass them.
                    # Wait, if image_url is "", it's a valid string. If price is "", Pydantic float("") fails. 
                    
                    product = Product(**row)
                    
                    if product.product_id in seen_ids:
                        summary["validation_errors"].append(f"Row {row_num}: Duplicate product_id '{product.product_id}' in CSV.")
                        summary["rejected_rows"] += 1
                    else:
                        products_to_insert.append(product)
                        seen_ids.add(product.product_id)
                        
                except ValidationError as e:
                    summary["rejected_rows"] += 1
                    # Format errors nicely
                    for error in e.errors():
                        field = error['loc'][0] if error['loc'] else 'Unknown'
                        msg = error['msg']
                        summary["validation_errors"].append(f"Row {row_num} - {field}: {msg}")

    except Exception as e:
         summary["validation_errors"].append(f"Error reading file: {str(e)}")
         return summary

    if summary["rejected_rows"] > 0 or len(summary["validation_errors"]) > 0:
        return summary

    try:
        insert_products_bulk(products_to_insert)
        summary["imported_rows"] = len(products_to_insert)
    except DuplicateProductError as e:
        summary["validation_errors"].append(f"Database error: {str(e)}")
        summary["rejected_rows"] = len(products_to_insert)
    except Exception as e:
        summary["validation_errors"].append(f"Database error: {str(e)}")
        summary["rejected_rows"] = len(products_to_insert)

    return summary
