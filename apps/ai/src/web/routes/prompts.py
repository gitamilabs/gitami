from fastapi import APIRouter, HTTPException

from src.prompts import get_prompt_info, list_prompts, reset_prompt, update_prompt
from src.web.schemas import PromptUpdateRequest

router = APIRouter(tags=["prompts"])


@router.get("/api/prompts")
async def list_all_prompts():
    """List all AI system prompts with descriptions, current text, and customization status."""
    return {"prompts": list_prompts()}


@router.get("/api/prompts/{key}")
async def get_single_prompt(key: str):
    """Get full details of a specific AI system prompt."""
    info = get_prompt_info(key)
    if not info:
        raise HTTPException(status_code=404, detail=f"Prompt '{key}' not found.")
    return info


@router.put("/api/prompts/{key}")
async def update_single_prompt(key: str, body: PromptUpdateRequest):
    """Update and persist an AI system prompt."""
    if not body.text or not body.text.strip():
        raise HTTPException(status_code=400, detail="Prompt text cannot be empty.")
    result = update_prompt(key, body.text)
    if not result:
        raise HTTPException(status_code=404, detail=f"Prompt '{key}' not found or could not be updated.")
    return {"status": "success", "prompt": result}


@router.post("/api/prompts/{key}/reset")
async def reset_single_prompt(key: str):
    """Reset an AI system prompt to its default original text."""
    result = reset_prompt(key)
    if not result:
        raise HTTPException(status_code=404, detail=f"Prompt '{key}' not found or could not be reset.")
    return {"status": "success", "prompt": result}
