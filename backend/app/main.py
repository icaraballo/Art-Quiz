from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import quiz

app = FastAPI(
    title="Art Quiz API",
    description="Quiz de arte con pinturas de los mejores museos del mundo",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(quiz.router)


@app.get("/")
def root():
    return {"status": "ok", "version": "0.2.0"}


@app.get("/salud")
def salud():
    return {"status": "ok"}
