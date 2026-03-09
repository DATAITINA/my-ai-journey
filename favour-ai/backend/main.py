import os
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel
from dotenv import load_dotenv
from google import genai
from google.genai import types

ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")
FRONTEND_DIR = ROOT_DIR / "frontend"

SYSTEM_PROMPT = (
    "You are a cheerful AI assistant built as a birthday gift for Favour. "
    "Be positive, friendly, playful, and supportive."
)

MODEL = (os.getenv("GEMINI_MODEL") or "gemini-2.5-flash-lite").strip()

app = FastAPI(title="Favour AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not set.")
    return genai.Client(api_key=api_key.strip())


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    user_message = (req.message or "").strip()
    if not user_message:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    try:
        client = get_client()
        response = await run_in_threadpool(
            client.models.generate_content,
            model=MODEL,
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.8,
                max_output_tokens=300,
            ),
        )

        reply_text = (response.text or "").strip()
        if not reply_text:
            reply_text = "I might be out of words. Want to try that again?"

        return ChatResponse(reply=reply_text)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Gemini request failed: {exc}")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")