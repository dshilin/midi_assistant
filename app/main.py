from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel
from loguru import logger

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
async def chat(req: ChatRequest):
    logger.info("chat request user={} msg_preview={}...", req.user_id, req.message[:60])
    from app.agent_fsm import run_fsm_agent

    response, state = await run_fsm_agent(req.user_id, req.message)

    logger.info("chat response user={} stage={}", req.user_id, state["stage"])
    return {
        "response": response,
        "state": state,
    }
