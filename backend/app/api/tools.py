from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.tools.registry import ToolRegistry
from app.core.security import get_current_user

router = APIRouter()


class ToolCallRequest(BaseModel):
    params: dict = {}


@router.get("")
async def list_tools():
    """List all available tools with their schemas and category groupings."""
    tools = []
    for t in ToolRegistry._tools.values():
        tools.append({
            "name": t.name,
            "description": t.description,
            "category": t.category,
            "is_async": t.is_async,
            "parameters": t.parameters,
        })
    return {
        "tools": tools,
        "categories": ToolRegistry.list_by_category(),
    }


@router.get("/{name}")
async def get_tool(name: str):
    """Get a specific tool's schema."""
    tool = ToolRegistry.get_tool(name)
    if not tool:
        raise HTTPException(404, f"Tool not found: {name}")
    return {
        "name": tool.name,
        "description": tool.description,
        "category": tool.category,
        "is_async": tool.is_async,
        "parameters": tool.parameters,
    }


@router.post("/{name}/call")
async def call_tool(name: str, req: ToolCallRequest, current_user: dict = Depends(get_current_user)):
    """Directly call a tool by name."""
    try:
        result = await ToolRegistry.execute(name, req.params)
        return {"status": "completed", "result": result}
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))
