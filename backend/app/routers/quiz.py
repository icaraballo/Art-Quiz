"""
Endpoints del quiz de arte.

GET  /quiz/pregunta   → cuadro aleatorio + pregunta + opciones
POST /quiz/respuesta  → valida respuesta, actualiza nivel
GET  /quiz/progreso   → estadísticas de la sesión
GET  /quiz/imagen     → proxy para imágenes de Wikimedia
"""

import json
import random
import re
import time
import unicodedata
import uuid
from collections import OrderedDict
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator

from app.limiter import limiter
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
PAINTINGS_IDX: dict[str, dict] = {p["id"]: p for p in PAINTINGS}

# ---------------------------------------------------------------------------
# Sesiones en memoria (LRU real + TTL por inactividad)
# ---------------------------------------------------------------------------

_sesiones: OrderedDict[str, dict] = OrderedDict()
_MAX_SESIONES = 500
_TTL_SESION = 3600          # 1 hora sin actividad
_DESCONOCIDOS = {"Museo desconocido", "Sin clasificar", "Desconocida", ""}
CAMPOS_VALIDOS = {"artista", "titulo", "museo", "movimiento", "tipo"}
_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def _limpiar_sesiones() -> None:
    ahora = time.time()
    caducadas = [sid for sid, e in _sesiones.items() if ahora - e["last_access"] > _TTL_SESION]
    for sid in caducadas:
        del _sesiones[sid]
    while len(_sesiones) >= _MAX_SESIONES:
        _sesiones.popitem(last=False)   # elimina la menos usada (FIFO = LRU cabeza)


def _nueva_sesion() -> tuple[str, dict]:
    _limpiar_sesiones()
    sid = str(uuid.uuid4())
    estado = {
        "nivel": 1,
        "racha": 0,
        "fallos_seguidos": 0,
        "vistos": [],           # lista de (cuadro_id, campo) ya preguntados
        "historial": [],
        "pregunta_actual": None,
        "last_access": time.time(),
    }
    _sesiones[sid] = estado
    return sid, estado


def _obtener_sesion(session_id: str) -> dict:
    if session_id not in _sesiones:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    estado = _sesiones[session_id]
    estado["last_access"] = time.time()
    _sesiones.move_to_end(session_id)   # LRU: marcar como más reciente
    return estado

# ---------------------------------------------------------------------------
# Levenshtein con normalización de acentos y puntuación
# ---------------------------------------------------------------------------

def _normalizar(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower().strip())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _levenshtein(a: str, b: str) -> int:
    a, b = _normalizar(a), _normalizar(b)
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


def _generar_opciones(
    campo: str,
    valor_correcto: str,
    nivel: int,
    painting: dict,
    db: list[dict],
) -> list[str]:
    cfg = config_nivel(nivel)

    if cfg.get("distractor") == "movimiento":
        pool = [
            _valor(p, campo)
            for p in db
            if _valor(p, campo) != valor_correcto
            and p.get("movimiento") == painting.get("movimiento")
        ]
        if len(pool) < 3:
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

    if campo == "titulo":
        for candidato in [valor, painting.get("titulo_original", "")]:
            if candidato and _levenshtein(respuesta, candidato) <= max_distancia:
                return True
        return False

    return _levenshtein(respuesta, valor) <= max_distancia

# ---------------------------------------------------------------------------
# Modelos Pydantic con validación de longitudes e inputs
# ---------------------------------------------------------------------------

class RespuestaRequest(BaseModel):
    session_id: str = Field(..., min_length=36, max_length=36)
    cuadro_id:  str = Field(..., min_length=1,  max_length=64)
    campo:      str = Field(..., min_length=1,  max_length=20)
    respuesta:  str = Field(..., max_length=200)
    timeout:    bool = False   # True = tiempo agotado, fuerza fallo y devuelve respuesta correcta

    @field_validator("session_id")
    @classmethod
    def _val_session(cls, v: str) -> str:
        if not _UUID_RE.match(v):
            raise ValueError("session_id inválido")
        return v

    @field_validator("campo")
    @classmethod
    def _val_campo(cls, v: str) -> str:
        if v not in CAMPOS_VALIDOS:
            raise ValueError("campo desconocido")
        return v

# ---------------------------------------------------------------------------
# GET /quiz/pregunta
# ---------------------------------------------------------------------------

_UUID_PATTERN = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"


@router.get("/pregunta")
@limiter.limit("120/minute")
def obtener_pregunta(
    request: Request,
    session_id: Optional[str] = Query(None, max_length=36, pattern=_UUID_PATTERN),
):
    if not PAINTINGS:
        raise HTTPException(status_code=503, detail="Base de datos no disponible")

    if session_id is None or session_id not in _sesiones:
        session_id, estado = _nueva_sesion()
    else:
        estado = _obtener_sesion(session_id)

    nivel = estado["nivel"]
    cfg = config_nivel(nivel)
    campos_posibles = cfg["campos"]
    campo = random.choice(campos_posibles)
    popularidad_min = cfg.get("popularidad_min", 1)

    # Anti-repetición por (cuadro_id, campo): cada combinación se pregunta una sola vez por sesión
    vistos: set[tuple[str, str]] = set(estado["vistos"])

    def _candidatos_para(pool: list[dict]) -> list[dict]:
        return [
            p for p in pool
            if (p["id"], campo) not in vistos
            and _valor(p, campo)
            and _valor(p, campo) not in _DESCONOCIDOS
            and p.get("popularidad", 1) >= popularidad_min
        ]

    candidatos = _candidatos_para(PAINTINGS)
    ya_visto = False
    if not candidatos:
        estado["vistos"] = []
        vistos = set()
        ya_visto = True
        candidatos = _candidatos_para(PAINTINGS)
    if not candidatos:
        candidatos = [p for p in PAINTINGS if _valor(p, campo) and _valor(p, campo) not in _DESCONOCIDOS]

    painting = random.choice(candidatos)
    estado["vistos"].append((painting["id"], campo))

    valor_correcto = _valor(painting, campo)
    modo = cfg["modo"]

    opciones = None
    if modo == "test":
        opciones = _generar_opciones(campo, valor_correcto, nivel, painting, PAINTINGS)

    # Guardar la pregunta activa para validar la respuesta posterior (evita cheating y doble envío)
    estado["pregunta_actual"] = {
        "cuadro_id": painting["id"],
        "campo": campo,
        "modo": modo,
        "opciones": opciones,
    }

    return {
        "session_id": session_id,
        "nivel": nivel,
        "cuadro": {
            "id": painting["id"],
            "image_url": painting["image_url"],
            # No enviar el título cuando es precisamente lo que se pregunta
            "titulo_display": painting["titulo"] if campo != "titulo" else None,
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
@limiter.limit("120/minute")
def validar_respuesta(request: Request, body: RespuestaRequest):
    estado = _obtener_sesion(body.session_id)

    # Verificar que la respuesta corresponde a la pregunta activa
    actual = estado.get("pregunta_actual")
    if not actual:
        raise HTTPException(status_code=409, detail="No hay pregunta activa")
    if actual["cuadro_id"] != body.cuadro_id or actual["campo"] != body.campo:
        raise HTTPException(status_code=409, detail="La respuesta no corresponde a la pregunta activa")
    # En timeout saltamos la validación de opción; en modo normal la aplicamos
    if not body.timeout and actual["modo"] == "test" and actual["opciones"] and body.respuesta not in actual["opciones"]:
        raise HTTPException(status_code=400, detail="Opción no válida")

    # Invalida la pregunta para impedir doble envío
    estado["pregunta_actual"] = None

    painting = PAINTINGS_IDX.get(body.cuadro_id)
    if painting is None:
        raise HTTPException(status_code=404, detail="Cuadro no encontrado")

    cfg = config_nivel(estado["nivel"])
    max_distancia = cfg.get("max_distancia", 0)

    # Timeout siempre es fallo; respuesta normal se evalúa normalmente
    correcto = False if body.timeout else _es_correcto(body.campo, body.respuesta, painting, max_distancia)

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
@limiter.limit("60/minute")
def obtener_progreso(
    request: Request,
    session_id: str = Query(..., max_length=36, pattern=_UUID_PATTERN),
):
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
        "historial": historial[-20:],
    }

# ---------------------------------------------------------------------------
# GET /quiz/imagen  — proxy para imágenes de Wikimedia
# ---------------------------------------------------------------------------

_DOMINIOS_PERMITIDOS = {"upload.wikimedia.org", "commons.wikimedia.org"}
_MAX_IMAGE_BYTES = 8 * 1024 * 1024   # 8 MB


@router.get("/imagen")
@limiter.limit("60/minute")
def proxy_imagen(request: Request, url: str):
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in _DOMINIOS_PERMITIDOS:
        raise HTTPException(status_code=400, detail="URL no permitida")
    try:
        with requests.get(
            url,
            stream=True,
            timeout=10,
            allow_redirects=False,
            headers={"User-Agent": "ArtQuizApp/1.0 (educational)"},
        ) as resp:
            if not resp.ok:
                raise HTTPException(status_code=502, detail="Error al obtener imagen")
            ctype = resp.headers.get("Content-Type", "")
            if not ctype.startswith("image/"):
                raise HTTPException(status_code=502, detail="Respuesta no es una imagen")
            buf = bytearray()
            for chunk in resp.iter_content(64 * 1024):
                buf.extend(chunk)
                if len(buf) > _MAX_IMAGE_BYTES:
                    raise HTTPException(status_code=413, detail="Imagen demasiado grande")
            return Response(
                content=bytes(buf),
                media_type=ctype,
                headers={
                    "Cache-Control": "public, max-age=86400, immutable",
                    "X-Content-Type-Options": "nosniff",
                },
            )
    except requests.RequestException:
        raise HTTPException(status_code=502, detail="No se pudo cargar la imagen")
