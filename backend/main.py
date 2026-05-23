from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager
import uvicorn

from database import init_db
from routers import ncbi, variants, pipeline, ai, annotation, reports


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    print("✅ GenomePipe Pro backend started")
    yield
    print("🛑 GenomePipe Pro backend stopped")


app = FastAPI(
    title="GenomePipe Pro API",
    description="Clinical Genomics Platform Backend — NCBI proxy, variant storage, NGS pipeline, Ollama AI",
    version="4.0.0",
    lifespan=lifespan,
)

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # tighten this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ncbi.router,       prefix="/api/ncbi",       tags=["NCBI"])
app.include_router(variants.router,   prefix="/api/variants",   tags=["Variants"])
app.include_router(pipeline.router,   prefix="/api/pipeline",   tags=["Pipeline"])
app.include_router(ai.router,         prefix="/api/ai",         tags=["AI (Ollama)"])
app.include_router(annotation.router, prefix="/api/annotation", tags=["Annotation"])
app.include_router(reports.router,    prefix="/api/reports",    tags=["Reports"])


@app.get("/", tags=["Health"])
async def root():
    return {
        "service": "GenomePipe Pro API",
        "version": "4.0.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
