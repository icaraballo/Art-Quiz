import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.limiter import limiter
from app.routers import quiz

app = FastAPI(
    title="Art Quiz API",
    description="Quiz de arte con pinturas de los mejores museos del mundo",
    version="0.2.0",
)

# En producción: CORS_ORIGINS=https://artquiz.app (sin comodín)
_origenes = os.getenv("CORS_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origenes,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
    allow_credentials=False,
    max_age=600,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.include_router(quiz.router)


@app.get("/")
def root():
    return {"status": "ok", "version": "0.2.0"}


@app.get("/salud")
def salud():
    return {"status": "ok"}
