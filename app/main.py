from typing import Dict, Any, Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, Response
from pydantic import BaseModel, Field
from app.config import settings
from app.database import init_db
from app.executor import execute_tool


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize minimal SQLite database configuration on startup
    init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    description="Merchant-as-a-Tool Agent Gateway API",
    version="0.1.0",
    lifespan=lifespan,
)


class ToolExecutionRequest(BaseModel):
    tool: str = Field(..., description="Name of the tool to execute")
    arguments: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Arguments to pass to the tool")


@app.get("/health", response_model=Dict[str, str])
def health_check() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/tools/execute")
def api_execute_tool(request: ToolExecutionRequest, response: Response):
    """Execute a tool dynamically."""
    result = execute_tool(request.tool, request.arguments)
    
    if not result.get("success"):
        error_code = result.get("error", {}).get("code")
        if error_code == "TOOL_NOT_FOUND":
            response.status_code = 404
        elif error_code == "INVALID_ARGUMENTS":
            response.status_code = 422
        else:
            response.status_code = 400
            
    return result
