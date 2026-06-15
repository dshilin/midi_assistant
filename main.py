from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = FastAPI(title="midi_assistant", description="AI-консультант по напольным покрытиям")


class ChatRequest(BaseModel):
    user_id: str
    message: str


@app.get("/")
async def index():
    return FileResponse("static/chat.html")


@app.post("/chat")
async def chat(req: ChatRequest):
    from agent_fsm import run_fsm_agent

    response, state = await run_fsm_agent(req.user_id, req.message)

    return {
        "response": response,
        "state": state,
    }
