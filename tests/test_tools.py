from app.tools import TOOLS, search_products_tool, get_product_tool

def test_tools_exist():
    assert "search_products" in TOOLS
    assert "get_product" in TOOLS
    assert len(TOOLS) == 10


def test_search_products_schema():
    tool = TOOLS["search_products"]
    assert tool.name == "search_products"
    assert "Search" in tool.description
    
    schema = tool.input_schema.model_json_schema()
    properties = schema.get("properties", {})
    
    # Check expected fields exist
    assert "query" in properties
    assert "category" in properties
    assert "min_price" in properties
    assert "max_price" in properties
    
    # Check that they are optional (not required)
    required = schema.get("required", [])
    assert "query" not in required
    assert "category" not in required
    assert "min_price" not in required
    assert "max_price" not in required
    
    # Verify types
    assert properties["query"].get("type") == "string" or "anyOf" in properties["query"]
    assert properties["min_price"].get("type") == "number" or "anyOf" in properties["min_price"]

    # Check output structure is defined
    assert "Product" in tool.output_structure

def test_get_product_schema():
    tool = TOOLS["get_product"]
    assert tool.name == "get_product"
    
    schema = tool.input_schema.model_json_schema()
    properties = schema.get("properties", {})
    
    # Check expected fields exist
    assert "product_id" in properties
    
    # Check that product_id is required
    required = schema.get("required", [])
    assert "product_id" in required

    # Verify type
    assert properties["product_id"].get("type") == "string"
    
    # Check output structure is defined
    assert "Product" in tool.output_structure
