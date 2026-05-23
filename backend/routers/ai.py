from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from models.schemas import AIAnalysisRequest, AIAnalysisResponse
from services.ollama_service import (
    check_ollama, stream_response, full_response, DEFAULT_MODEL
)

router = APIRouter()


@router.get("/status")
async def ollama_status():
    """Check if Ollama is running and list available models."""
    return await check_ollama()


@router.post("/analyze/stream")
async def analyze_stream(req: AIAnalysisRequest):
    """
    Stream Ollama response tokens as Server-Sent Events (SSE).
    The frontend EventSource connects here for real-time token streaming.
    """
    status = await check_ollama()
    if not status["online"]:
        raise HTTPException(
            503,
            "Ollama is offline. Run: ollama serve  (then: ollama pull llama3)"
        )

    async def event_generator():
        try:
            async for token in stream_response(
                message=req.message,
                mode=req.mode,
                history=req.history,
                variants=req.variants,
                model=req.model or DEFAULT_MODEL,
            ):
                # SSE format
                yield f"data: {token}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: [ERROR] {str(e)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/analyze", response_model=AIAnalysisResponse)
async def analyze_full(req: AIAnalysisRequest):
    """
    Non-streaming Ollama analysis — returns complete response at once.
    Useful for report generation and batch analysis.
    """
    status = await check_ollama()
    if not status["online"]:
        raise HTTPException(
            503,
            "Ollama is offline. Run: ollama serve  (then: ollama pull llama3)"
        )

    response_text = await full_response(
        message=req.message,
        mode=req.mode,
        history=req.history,
        variants=req.variants,
        model=req.model or DEFAULT_MODEL,
    )

    return AIAnalysisResponse(
        response=response_text,
        model=req.model or DEFAULT_MODEL,
        mode=req.mode,
    )


@router.get("/models")
async def list_models():
    """List all models available in the local Ollama installation."""
    status = await check_ollama()
    if not status["online"]:
        return {"online": False, "models": [], "recommended": "llama3"}
    return {
        "online": True,
        "models": status["models"],
        "recommended": "llama3",
        "biomedical": ["biomistral", "medllama2", "meditron"],
    }
