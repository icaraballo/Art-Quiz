"""
Calcula el nivel de dificultad del quiz según la confianza del modelo.

Niveles:
  - facil:   confianza >= 0.80  → El modelo está muy seguro
  - medio:   confianza 0.50–0.79 → Duda razonable
  - dificil: confianza < 0.50   → El modelo no está seguro
"""


def calcular_dificultad(confianza: float) -> str:
    if confianza >= 0.80:
        return "facil"
    elif confianza >= 0.50:
        return "medio"
    else:
        return "dificil"


def descripcion_dificultad(nivel: str) -> str:
    descripciones = {
        "facil": "El cuadro es muy reconocible. 4 opciones con pistas visuales.",
        "medio": "El cuadro tiene características similares a otros. 4 opciones parecidas.",
        "dificil": "El modelo no está seguro. Escribe el nombre del autor sin pistas.",
    }
    return descripciones.get(nivel, "Nivel desconocido")
