import base64
import io
import json
import random
from pathlib import Path

from fastapi import APIRouter, HTTPException
from PIL import Image
from pydantic import BaseModel

from app.models.clip_model import modelo_clip
from app.models.difficulty import calcular_dificultad

router = APIRouter(prefix="/predict", tags=["predicción"])

# Cargar BD de cuadros al arrancar
DATA_PATH = Path(__file__).parent.parent / "data" / "paintings.json"

def cargar_paintings():
    if not DATA_PATH.exists():
        return []
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        datos = json.load(f)
    return datos.get("paintings", [])

PAINTINGS = cargar_paintings()


class PredictRequest(BaseModel):
    image: str      # Base64
    top_k: int = 3


class PredictResponse(BaseModel):
    resultado_principal: dict
    quiz: dict
    total_cuadros_bd: int


@router.post("/", response_model=PredictResponse)
async def predecir(request: PredictRequest):
    if not PAINTINGS:
        raise HTTPException(
            status_code=503,
            detail="Base de datos vacía. Ejecuta primero scripts/fetch_met_museum.py"
        )

    # Decodificar imagen base64
    try:
        image_bytes = base64.b64decode(request.image)
        imagen = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception:
        raise HTTPException(status_code=400, detail="Imagen inválida o mal codificada")

    # Obtener predicciones del modelo
    resultados = modelo_clip.predecir(imagen, PAINTINGS, top_k=request.top_k)

    if not resultados:
        raise HTTPException(status_code=500, detail="El modelo no devolvió resultados")

    mejor = resultados[0]
    dificultad = calcular_dificultad(mejor["confianza"])

    # Generar opciones incorrectas para el quiz
    ids_correctos = {r["cuadro"]["id"] for r in resultados}
    pool_incorrectos = [p for p in PAINTINGS if p["id"] not in ids_correctos]
    opciones_incorrectas = random.sample(
        pool_incorrectos, min(3, len(pool_incorrectos))
    )

    return {
        "resultado_principal": {
            "confianza": round(mejor["confianza"], 3),
            "cuadro": mejor["cuadro"],
            "dificultad": dificultad
        },
        "quiz": {
            "dificultad": dificultad,
            "opciones_incorrectas": [
                {"artista": p["artista"], "titulo": p["titulo"]}
                for p in opciones_incorrectas
            ]
        },
        "total_cuadros_bd": len(PAINTINGS)
    }
