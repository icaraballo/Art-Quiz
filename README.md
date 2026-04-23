# Art Quiz

App móvil de quiz sobre arte. Se muestra la imagen de un cuadro y el usuario adivina el título, autor, año, movimiento artístico y museo.

---

## Concepto

- **Niveles bajos:** tipo test con 4 opciones
- **Niveles altos:** escritura libre con tolerancia de 1-2 letras (distancia de Levenshtein)
- **Dificultad adaptativa:** sube o baja automáticamente según los aciertos del usuario
- **Base de datos:** 500 pinturas de dominio público del Art Institute of Chicago

---

## Stack

| Capa | Tecnología |
|------|-----------|
| Mobile | React Native + Expo |
| Backend | Python + FastAPI |
| Datos | Art Institute of Chicago API |

---

## Estructura del proyecto

```
art-quiz/
├── backend/
│   ├── app/
│   │   ├── main.py                  # Entry point FastAPI
│   │   ├── routers/
│   │   │   └── predict.py           # Endpoints del quiz
│   │   ├── models/
│   │   │   └── difficulty.py        # Lógica de dificultad adaptativa
│   │   └── data/
│   │       └── paintings.json       # 500 cuadros normalizados
│   ├── scripts/
│   │   ├── fetch_met_museum.py      # Descarga cuadros del ARTIC
│   │   ├── translate_titles.py      # Traduce títulos al castellano
│   │   └── validate_db.py           # Valida paintings.json
│   └── requirements.txt
│
└── mobile/
    ├── app/
    │   └── (tabs)/
    │       ├── quiz.tsx             # Pantalla quiz
    │       └── historial.tsx        # Historial de partidas
    ├── services/
    │   └── api.ts                   # Llamadas al backend
    └── package.json
```

---

## Schema de paintings.json

```json
{
  "paintings": [
    {
      "id": "nenufares-claude-monet",
      "titulo": "Nenúfares",
      "artista": "Claude Monet",
      "anio": 1906,
      "movimiento": "Impresionismo",
      "museo": "Art Institute of Chicago",
      "image_url": "https://www.artic.edu/iiif/2/.../full/600,/0/default.jpg"
    }
  ]
}
```

---

## Cómo arrancar el backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Regenerar la base de datos (opcional, ya incluida):
```bash
python scripts/fetch_met_museum.py          # descarga 500 cuadros
python scripts/translate_titles.py          # traduce títulos al castellano
```

Arrancar el servidor:
```bash
uvicorn app.main:app --reload --port 8000
```

---

## API Endpoints (Semana 2)

### `GET /quiz/pregunta`
Devuelve un cuadro aleatorio con opciones incorrectas generadas.

```json
{
  "cuadro": {
    "id": "...",
    "image_url": "...",
    "nivel": 2
  },
  "pregunta": "¿Quién pintó este cuadro?",
  "opciones": ["Claude Monet", "Pierre Renoir", "Paul Gauguin", "Edgar Degas"]
}
```

### `POST /quiz/respuesta`
Recibe la respuesta del usuario y devuelve si es correcta.

```json
{ "cuadro_id": "...", "campo": "artista", "respuesta": "Claude Monet" }
```

### `GET /quiz/progreso`
Devuelve el nivel actual y el historial de aciertos.

---

## Hoja de ruta

| Semana | Objetivo |
|--------|---------|
| ~~1~~ | Backend: datos descargados, normalizados y traducidos al castellano ✅ |
| 2 | Backend: endpoints `/quiz/pregunta`, `/quiz/respuesta`, `/quiz/progreso` + tolerancia Levenshtein |
| 3 | Mobile: pantalla quiz con imagen, 4 opciones, animaciones acierto/fallo |
| 4 | Mobile: progresión de nivel, escritura libre en niveles altos, historial |
| 5 | Polish + testing + deploy (Railway o Render) |
