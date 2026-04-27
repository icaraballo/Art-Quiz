"""
Configuración de niveles y lógica de dificultad adaptativa.

La dificultad tiene dos ejes:
  1. POPULARIDAD del cuadro (sitelinks Wikipedia): niveles bajos = cuadros famosos
  2. CAMPOS disponibles: se amplían progresivamente (artista/título → movimiento → museo)

En cada pregunta el backend elige aleatoriamente entre los campos del nivel.
Niveles 1-8: tipo test (4 opciones).
Niveles 9-10: escritura libre, tolerancia Levenshtein.
"""

NIVELES: dict[int, dict] = {
    # Nivel 1: pinturas icónicas, solo artista
    1:  {"campos": ["artista"],                                    "modo": "test",  "distractor": "global",     "popularidad_min": 4},
    # Nivel 2: pinturas icónicas, artista o título
    2:  {"campos": ["artista", "titulo"],                          "modo": "test",  "distractor": "global",     "popularidad_min": 4},
    # Nivel 3: pinturas conocidas, artista o título
    3:  {"campos": ["artista", "titulo"],                          "modo": "test",  "distractor": "global",     "popularidad_min": 3},
    # Nivel 4: pinturas conocidas, se añade movimiento
    4:  {"campos": ["artista", "titulo", "movimiento"],            "modo": "test",  "distractor": "global",     "popularidad_min": 3},
    # Nivel 5: pinturas moderadas, distractores del mismo movimiento
    5:  {"campos": ["artista", "titulo", "movimiento"],            "modo": "test",  "distractor": "movimiento", "popularidad_min": 2},
    # Nivel 6: pinturas moderadas, se añade museo
    6:  {"campos": ["artista", "titulo", "movimiento", "museo"],   "modo": "test",  "distractor": "movimiento", "popularidad_min": 2},
    # Nivel 7: todas las pinturas, todos los campos
    7:  {"campos": ["artista", "titulo", "movimiento", "museo"],   "modo": "test",  "distractor": "movimiento", "popularidad_min": 1},
    # Nivel 8: todas las pinturas, se añade tipo de material
    8:  {"campos": ["artista", "titulo", "movimiento", "museo", "tipo"], "modo": "test", "distractor": "movimiento", "popularidad_min": 1},
    # Nivel 9: escritura libre, artista o título, tolerancia alta
    9:  {"campos": ["artista", "titulo"],                          "modo": "libre", "max_distancia": 2,         "popularidad_min": 1},
    # Nivel 10: escritura libre, todos los campos, tolerancia baja
    10: {"campos": ["artista", "titulo", "movimiento", "museo"],   "modo": "libre", "max_distancia": 1,         "popularidad_min": 1},
}

PREGUNTAS: dict[str, str] = {
    "artista":    "¿Quién pintó este cuadro?",
    "titulo":     "¿Cómo se llama este cuadro?",
    "museo":      "¿En qué museo se encuentra este cuadro?",
    "movimiento": "¿A qué movimiento artístico pertenece este cuadro?",
    "tipo":       "¿Con qué técnica fue pintado este cuadro?",
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
