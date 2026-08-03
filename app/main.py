from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from loguru import logger

from app.agent_fsm import run_fsm_agent
from app.clients import get_client

app = FastAPI(title="midi_assistant", description="AI-консультант по напольным покрытиям")

logger.info("starting midi_assistant server")


class ChatRequest(BaseModel):
    user_id: str
    message: str


@app.get("/")
async def index():
    logger.debug("serving chat.html")
    return FileResponse("static/chat.html")


@app.post("/chat")
async def chat_legacy(req: ChatRequest):
    logger.info("chat request user={} msg_preview={}...", req.user_id, req.message[:60])

    response, state = await run_fsm_agent(f"web:midi:{req.user_id}", req.message, client_slug="midi")

    logger.info("chat response user={} stage={}", req.user_id, state["stage"])
    return {
        "response": response,
        "state": state,
    }


@app.get("/{slug}")
async def site_index(slug: str):
    if get_client(slug) is None:
        return JSONResponse({"detail": "client not found"}, status_code=404)
    return FileResponse("static/chat.html")


@app.post("/{slug}/chat")
async def site_chat(slug: str, req: ChatRequest):
    logger.info("chat request slug={} user={} msg_preview={}...", slug, req.user_id, req.message[:60])
    if get_client(slug) is None:
        return JSONResponse({"detail": "client not found"}, status_code=404)
    response, state = await run_fsm_agent(f"web:{slug}:{req.user_id}", req.message, client_slug=slug)
    return {"response": response, "state": state}
