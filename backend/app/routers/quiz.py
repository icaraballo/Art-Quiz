"""
Endpoints del quiz de arte.

GET  /quiz/pregunta   → cuadro aleatorio + pregunta + opciones
POST /quiz/respuesta  → valida respuesta, actualiza nivel
GET  /quiz/progreso   → estadísticas de la sesión
"""

import json
import random
import uuid
from pathlib import Path
from typing import Optional

import requests
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from app.models.difficulty import (
    PREGUNTAS,
    actualizar_nivel,
    config_nivel,
)

router = APIRouter(prefix="/quiz", tags=["quiz"])

# ---------------------------------------------------------------------------
# Base de datos de cuadros (se carga una sola vez al arrancar)
# ---------------------------------------------------------------------------

DATA_PATH = Path(__file__).parent.parent / "data" / "paintings.json"


def _cargar_paintings() -> list[dict]:
    if not DATA_PATH.exists():
        return []
    with open(DATA_PATH, encoding="utf-8") as f:
        datos = json.load(f)
    return datos.get("paintings", [])


PAINTINGS: list[dict] = _cargar_paintings()
# Índice rápido id → painting
PAINTINGS_IDX: dict[str, dict] = {p["id"]: p for p in PAINTINGS}

# ---------------------------------------------------------------------------
# Sesiones en memoria
# ---------------------------------------------------------------------------

_sesiones: dict[str, dict] = {}


def _nueva_sesion() -> tuple[str, dict]:
    sid = str(uuid.uuid4())
    estado = {
        "nivel": 1,
        "racha": 0,
        "fallos_seguidos": 0,
        "vistos": [],
        "historial": [],
    }
    _sesiones[sid] = estado
    return sid, estado


def _obtener_sesion(session_id: str) -> dict:
    if session_id not in _sesiones:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    return _sesiones[session_id]

# ---------------------------------------------------------------------------
# Levenshtein (puro Python, sin dependencias)
# ---------------------------------------------------------------------------

def _levenshtein(a: str, b: str) -> int:
    a, b = a.lower().strip(), b.lower().strip()
    if a == b:
        return 0
    m, n = len(a), len(b)
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev, dp[0] = dp[0], i
        for j in range(1, n + 1):
            temp = dp[j]
            dp[j] = prev if a[i - 1] == b[j - 1] else 1 + min(dp[j], dp[j - 1], prev)
            prev = temp
    return dp[n]

# ---------------------------------------------------------------------------
# Generación de distractores
# ---------------------------------------------------------------------------

def _valor(painting: dict, campo: str) -> str:
    v = painting.get(campo)
    return str(v) if v is not None else ""


def _generar_opciones_anio(anio_correcto: int, margen: int) -> list[str]:
    opciones: set[str] = {str(anio_correcto)}
    intentos = 0
    step = max(5, margen // 4)
    while len(opciones) < 4 and intentos < 200:
        candidato = anio_correcto + random.randint(-margen, margen)
        candidato = (candidato // step) * step  # redondear para que quede creíble
        if candidato > 0 and str(candidato) != str(anio_correcto):
            opciones.add(str(candidato))
        intentos += 1
    lista = list(opciones)
    random.shuffle(lista)
    return lista


def _generar_opciones(
    campo: str,
    valor_correcto: str,
    nivel: int,
    painting: dict,
    db: list[dict],
) -> list[str]:
    cfg = config_nivel(nivel)

    if campo == "anio":
        anio = int(valor_correcto) if valor_correcto.isdigit() else 1800
        return _generar_opciones_anio(anio, cfg.get("margen", 30))

    # Construir pool de distractores
    if cfg.get("distractor") == "movimiento":
        pool = [
            _valor(p, campo)
            for p in db
            if _valor(p, campo) != valor_correcto
            and p.get("movimiento") == painting.get("movimiento")
        ]
        if len(pool) < 3:  # fallback a pool global si no hay suficientes
            pool = [_valor(p, campo) for p in db if _valor(p, campo) != valor_correcto]
    else:
        pool = [_valor(p, campo) for p in db if _valor(p, campo) != valor_correcto]

    pool = [v for v in set(pool) if v]
    distractores = random.sample(pool, min(3, len(pool)))
    opciones = [valor_correcto] + distractores
    random.shuffle(opciones)
    return opciones

# ---------------------------------------------------------------------------
# Validación de respuesta
# ---------------------------------------------------------------------------

def _es_correcto(campo: str, respuesta: str, painting: dict, max_distancia: int) -> bool:
    valor = _valor(painting, campo)
    respuesta = respuesta.strip()

    if campo == "anio":
        try:
            return abs(int(respuesta) - int(valor)) <= 5
        except ValueError:
            return False

    if campo == "titulo":
        # Acepta tanto titulo (español) como titulo_original
        for candidato in [valor, painting.get("titulo_original", "")]:
            if _levenshtein(respuesta, candidato) <= max_distancia:
                return True
        return False

    return _levenshtein(respuesta, valor) <= max_distancia

# ---------------------------------------------------------------------------
# Modelos Pydantic
# ---------------------------------------------------------------------------

class RespuestaRequest(BaseModel):
    session_id: str
    cuadro_id: str
    campo: str
    respuesta: str


# ---------------------------------------------------------------------------
# GET /quiz/pregunta
# ---------------------------------------------------------------------------

@router.get("/pregunta")
def obtener_pregunta(session_id: Optional[str] = None):
    if not PAINTINGS:
        raise HTTPException(
            status_code=503,
            detail="Base de datos vacía. Ejecuta scripts/fetch_wikidata.py",
        )

    # Crear sesión si no existe
    if session_id is None or session_id not in _sesiones:
        session_id, estado = _nueva_sesion()
    else:
        estado = _sesiones[session_id]

    nivel = estado["nivel"]
    cfg = config_nivel(nivel)
    campos_posibles = cfg["campos"]
    campo = random.choice(campos_posibles)
    popularidad_min = cfg.get("popularidad_min", 1)

    # Elegir cuadro que no se haya preguntado ya en esta sesión
    vistos = set(estado["vistos"])
    _DESCONOCIDOS = {"Museo desconocido", "Sin clasificar", "Desconocida", ""}

    def _candidatos_para(pool: list[dict]) -> list[dict]:
        return [
            p for p in pool
            if p["id"] not in vistos
            and _valor(p, campo)
            and _valor(p, campo) not in _DESCONOCIDOS
            and p.get("popularidad", 1) >= popularidad_min
        ]

    candidatos = _candidatos_para(PAINTINGS)
    ya_visto = False
    if not candidatos:
        # Pool agotado — reiniciar vistos y marcar como repetición
        estado["vistos"] = []
        vistos = set()
        ya_visto = True
        candidatos = _candidatos_para(PAINTINGS)
    if not candidatos:
        # Fallback sin filtro de popularidad (pool muy pequeño)
        candidatos = [p for p in PAINTINGS if _valor(p, campo) and _valor(p, campo) not in _DESCONOCIDOS]

    painting = random.choice(candidatos)
    estado["vistos"].append(painting["id"])

    valor_correcto = _valor(painting, campo)
    modo = cfg["modo"]

    opciones = None
    if modo == "test":
        opciones = _generar_opciones(campo, valor_correcto, nivel, painting, PAINTINGS)

    return {
        "session_id": session_id,
        "nivel": nivel,
        "cuadro": {
            "id": painting["id"],
            "image_url": painting["image_url"],
            "titulo_display": painting["titulo"],
        },
        "pregunta": PREGUNTAS[campo],
        "campo": campo,
        "modo": modo,
        "opciones": opciones,
        "ya_visto": ya_visto,
    }


# ---------------------------------------------------------------------------
# POST /quiz/respuesta
# ---------------------------------------------------------------------------

@router.post("/respuesta")
def validar_respuesta(body: RespuestaRequest):
    estado = _obtener_sesion(body.session_id)

    painting = PAINTINGS_IDX.get(body.cuadro_id)
    if painting is None:
        raise HTTPException(status_code=404, detail="Cuadro no encontrado")

    cfg = config_nivel(estado["nivel"])
    max_distancia = cfg.get("max_distancia", 0)

    correcto = _es_correcto(body.campo, body.respuesta, painting, max_distancia)

    nivel_anterior = estado["nivel"]
    nuevo_nivel, nueva_racha, nuevos_fallos = actualizar_nivel(
        estado["nivel"],
        estado["racha"],
        estado["fallos_seguidos"],
        correcto,
    )
    estado["nivel"] = nuevo_nivel
    estado["racha"] = nueva_racha
    estado["fallos_seguidos"] = nuevos_fallos
    estado["historial"].append({
        "cuadro_id": body.cuadro_id,
        "campo": body.campo,
        "respuesta": body.respuesta,
        "correcto": correcto,
    })

    return {
        "correcto": correcto,
        "respuesta_correcta": _valor(painting, body.campo),
        "titulo_original": painting.get("titulo_original", ""),
        "titulo": painting.get("titulo", ""),
        "artista": painting.get("artista", ""),
        "nivel_anterior": nivel_anterior,
        "nivel_nuevo": nuevo_nivel,
        "racha": nueva_racha,
    }


# ---------------------------------------------------------------------------
# GET /quiz/progreso
# ---------------------------------------------------------------------------

@router.get("/progreso")
def obtener_progreso(session_id: str):
    estado = _obtener_sesion(session_id)

    historial = estado["historial"]
    total = len(historial)
    aciertos = sum(1 for h in historial if h["correcto"])

    return {
        "session_id": session_id,
        "nivel": estado["nivel"],
        "total_preguntas": total,
        "total_aciertos": aciertos,
        "porcentaje": round(100 * aciertos / total) if total else 0,
        "racha_actual": estado["racha"],
        "historial": historial[-20:],  # últimas 20 entradas
    }


# ---------------------------------------------------------------------------
# GET /quiz/imagen  — proxy para imágenes de Wikimedia
# ---------------------------------------------------------------------------

@router.get("/imagen")
def proxy_imagen(url: str):
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "ArtQuizApp/1.0 (educational)"})
        if not resp.ok:
            raise HTTPException(status_code=502, detail="Error al obtener imagen")
        content_type = resp.headers.get("Content-Type", "image/jpeg")
        return Response(content=resp.content, media_type=content_type)
    except requests.RequestException:
        raise HTTPException(status_code=502, detail="No se pudo cargar la imagen")
