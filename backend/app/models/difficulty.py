"""
Configuración de niveles y lógica de dificultad adaptativa.

Niveles 1-8: tipo test (4 opciones).
Niveles 9-10: escritura libre con tolerancia Levenshtein.
"""

NIVELES: dict[int, dict] = {
    1:  {"campo": "movimiento", "modo": "test",  "distractor": "global"},
    2:  {"campo": "epoca",      "modo": "test",  "distractor": "global"},
    3:  {"campo": "museo",      "modo": "test",  "distractor": "global"},
    4:  {"campo": "artista",    "modo": "test",  "distractor": "global"},
    5:  {"campo": "titulo",     "modo": "test",  "distractor": "global"},
    6:  {"campo": "artista",    "modo": "test",  "distractor": "movimiento"},
    7:  {"campo": "titulo",     "modo": "test",  "distractor": "movimiento"},
    8:  {"campo": "anio",       "modo": "test",  "margen": 30},
    9:  {"campo": "artista",    "modo": "libre", "max_distancia": 2},
    10: {"campo": "titulo",     "modo": "libre", "max_distancia": 2},
}

PREGUNTAS: dict[str, str] = {
    "movimiento": "¿A qué movimiento artístico pertenece este cuadro?",
    "epoca":      "¿A qué época pertenece este cuadro?",
    "museo":      "¿En qué museo se encuentra este cuadro?",
    "artista":    "¿Quién pintó este cuadro?",
    "titulo":     "¿Cómo se llama este cuadro?",
    "anio":       "¿En qué año fue pintado este cuadro?",
}

NIVEL_MIN = 1
NIVEL_MAX = 10
ACIERTOS_PARA_SUBIR = 3
FALLOS_PARA_BAJAR = 2


def config_nivel(nivel: int) -> dict:
    return NIVELES.get(nivel, NIVELES[1])


def actualizar_nivel(
    nivel: int,
    racha: int,
    fallos_seguidos: int,
    correcto: bool,
) -> tuple[int, int, int]:
    """Devuelve (nivel_nuevo, racha_nueva, fallos_seguidos_nuevos)."""
    if correcto:
        racha += 1
        fallos_seguidos = 0
        if racha >= ACIERTOS_PARA_SUBIR:
            return min(nivel + 1, NIVEL_MAX), 0, 0
    else:
        fallos_seguidos += 1
        racha = 0
        if fallos_seguidos >= FALLOS_PARA_BAJAR:
            return max(nivel - 1, NIVEL_MIN), 0, 0
    return nivel, racha, fallos_seguidos
