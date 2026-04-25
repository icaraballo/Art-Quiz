"""
Configuración de niveles y lógica de dificultad adaptativa.

La dificultad depende de la POPULARIDAD del cuadro (campo `popularidad` 1-5
basado en sitelinks de Wikipedia), no del tipo de pregunta.

Niveles 1-8: tipo test (4 opciones), de pinturas icónicas a desconocidas.
Niveles 9-10: escritura libre con tolerancia Levenshtein, cualquier pintura.
"""

NIVELES: dict[int, dict] = {
    # Pinturas icónicas del dataset (popularidad 4: 40-99 sitelinks — ~18 cuadros)
    1:  {"campo": "artista", "modo": "test",  "distractor": "global",     "popularidad_min": 4},
    2:  {"campo": "titulo",  "modo": "test",  "distractor": "global",     "popularidad_min": 4},
    # Pinturas bastante conocidas (popularidad ≥ 3: 15+ sitelinks — ~235 cuadros)
    3:  {"campo": "artista", "modo": "test",  "distractor": "global",     "popularidad_min": 3},
    4:  {"campo": "titulo",  "modo": "test",  "distractor": "global",     "popularidad_min": 3},
    # Pinturas algo conocidas (popularidad ≥ 2: 5+ sitelinks — ~733 cuadros)
    5:  {"campo": "artista", "modo": "test",  "distractor": "movimiento", "popularidad_min": 2},
    6:  {"campo": "titulo",  "modo": "test",  "distractor": "movimiento", "popularidad_min": 2},
    # Cualquier pintura, opción múltiple (267 muy oscuras se añaden aquí)
    7:  {"campo": "artista", "modo": "test",  "distractor": "movimiento", "popularidad_min": 1},
    8:  {"campo": "titulo",  "modo": "test",  "distractor": "movimiento", "popularidad_min": 1},
    # Cualquier pintura, escritura libre
    9:  {"campo": "artista", "modo": "libre", "max_distancia": 2,         "popularidad_min": 1},
    10: {"campo": "titulo",  "modo": "libre", "max_distancia": 2,         "popularidad_min": 1},
}

PREGUNTAS: dict[str, str] = {
    "artista":    "¿Quién pintó este cuadro?",
    "titulo":     "¿Cómo se llama este cuadro?",
    "anio":       "¿En qué año fue pintado este cuadro?",
    "museo":      "¿En qué museo se encuentra este cuadro?",
    "movimiento": "¿A qué movimiento artístico pertenece este cuadro?",
    "epoca":      "¿A qué época pertenece este cuadro?",
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
