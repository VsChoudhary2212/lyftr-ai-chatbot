
import json
import logging

from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware

from app.config import (
    ALLOWED_ORIGINS,
    ENABLE_FAILURE_SIMULATION,
    DEFAULT_SYSTEM_PROMPT,
    LLM_API_KEYS
)

from app.database import (
    init_db,
    get_session,
    create_session,
    update_system_prompt,
    get_messages,
    save_message,
    list_sessions
)

from app.schemas import ChatRequest, ChatResponse
from app.llm_service import generate_response


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("lyftr-ai")


app = FastAPI(
    title="Lyftr AI Chatbot API",
    description="LLM Chatbot with Key Failover and Response Caching",
    version="1.0.0"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"]
)


@app.on_event("startup")
def startup():
    init_db()
    logger.info("SQLite database initialized")


@app.get("/")
def root():
    return {
        "message": "Welcome to Lyftr AI API",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health")
def health():
    try:
        init_db()

        if len(LLM_API_KEYS) < 2:
            raise HTTPException(
                status_code=503,
                detail="At least two API keys are required"
            )

        return {
            "status": "ok",
            "keys_configured": len(LLM_API_KEYS),
            "cache_enabled": True
        }

    except HTTPException:
        raise

    except Exception:
        logger.exception("Health check failed")
        raise HTTPException(
            status_code=503,
            detail="Backend or database unavailable"
        )


@app.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    x_simulate_failure: str | None = Header(
        default=None,
        alias="X-Simulate-Failure"
    )
):
    session_id = request.session_id
    message = request.message.strip()

    if not message:
        raise HTTPException(
            status_code=422,
            detail="Message cannot be empty"
        )

    if len(message) > 4000:
        raise HTTPException(
            status_code=422,
            detail="Message cannot exceed 4000 characters"
        )

    if x_simulate_failure and not ENABLE_FAILURE_SIMULATION:
        raise HTTPException(
            status_code=403,
            detail="Failure simulation is disabled"
        )

    try:
        session = get_session(session_id)

        if session is None:
            system_prompt = (
                request.system_prompt.strip()
                if request.system_prompt and request.system_prompt.strip()
                else DEFAULT_SYSTEM_PROMPT
            )
        else:
            system_prompt = session["system_prompt"]

            if request.system_prompt is not None:
                system_prompt = (
                    request.system_prompt.strip()
                    or DEFAULT_SYSTEM_PROMPT
                )

        history = get_messages(session_id) if session else []

        llm_messages = [
            {
                "role": "system",
                "content": system_prompt
            }
        ]

        for item in history:
            llm_messages.append({
                "role": item["role"],
                "content": item["content"]
            })

        llm_messages.append({
            "role": "user",
            "content": message
        })

        result = generate_response(
            messages=llm_messages,
            failure_header=x_simulate_failure
        )

        reply = result["reply"]
        metadata = result["metadata"]

        # Create or update session only after successful inference.
        if session is None:
            create_session(session_id, system_prompt)

        elif request.system_prompt is not None:
            update_system_prompt(session_id, system_prompt)

        save_message(session_id, "user", message)

        save_message(
            session_id,
            "assistant",
            reply,
            json.dumps(metadata)
        )

        return {
            "session_id": session_id,
            "reply": reply,
            "metadata": metadata
        }

    except RuntimeError:
        raise HTTPException(
            status_code=503,
            detail="all providers unavailable"
        )

    except HTTPException:
        raise

    except Exception:
        logger.exception("Chat request failed")

        raise HTTPException(
            status_code=503,
            detail="Unable to process request"
        )


# Return all saved conversations.
@app.get("/sessions")
def all_sessions():
    sessions = list_sessions()

    return {
        "sessions": [
            {
                "session_id": item["session_id"],
                "created_at": item["created_at"],
                "title": (
                    item["title"] or "New conversation"
                )[:100],
                "last_message": item["last_message"] or "",
                "message_count": item["message_count"]
            }
            for item in sessions
        ]
    }


# Return the complete messages of one conversation.
@app.get("/sessions/{session_id}/messages")
def session_messages(session_id: str):
    session = get_session(session_id)

    if session is None:
        raise HTTPException(
            status_code=404,
            detail="session not found"
        )

    history = get_messages(session_id)

    messages = []

    for item in history:
        message = {
            "role": item["role"],
            "content": item["content"]
        }

        if item["role"] == "assistant":
            message["metadata"] = (
                json.loads(item["metadata"])
                if item["metadata"]
                else {}
            )

        messages.append(message)

    return {
        "session_id": session_id,
        "messages": messages
    }
