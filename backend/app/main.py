from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import predict

app = FastAPI(
    title="Art Quiz API",
    description="Reconocimiento de cuadros famosos mediante IA",
    version="0.1.0"
)

# CORS para que el móvil pueda llamar al servidor local
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, restringir a la IP del móvil
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(predict.router)


@app.get("/")
def root():
    return {"status": "ok", "mensaje": "Art Quiz API funcionando"}


@app.get("/salud")
def salud():
    return {"status": "ok"}
