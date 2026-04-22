# 🎨 Art Quiz

App móvil que reconoce cuadros famosos usando IA. El jugador fotografía o sube una imagen de un cuadro y la app identifica el título, autor, año y movimiento artístico, generando un quiz con dificultad adaptativa.

---

## Stack Tecnológico

| Capa | Tecnología |
|------|-----------|
| Mobile | React Native + Expo |
| Backend | Python + FastAPI |
| IA | CLIP (OpenAI, open source) |
| Datos | Met Museum API + WikiArt |

---

## Cómo arrancar el proyecto (primer día en casa)

### 1. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate        # En Mac/Linux
pip install -r requirements.txt
```

Descargar los primeros 500 cuadros:
```bash
python scripts/fetch_met_museum.py
```

Pre-calcular embeddings (solo se hace una vez):
```bash
python scripts/precompute_embeddings.py
```

Arrancar el servidor:
```bash
uvicorn app.main:app --reload --port 8000
```

Verificar que funciona:
```
http://localhost:8000/docs   ← Swagger UI automático
```

---

### 2. Mobile

```bash
cd mobile
npm install
npx expo start
```

Escanea el QR con la app Expo Go en el móvil, o pulsa `i` para el simulador iOS.

---

## Estructura del proyecto

```
art-quiz/
├── backend/
│   ├── app/
│   │   ├── main.py                  # Entry point FastAPI
│   │   ├── routers/
│   │   │   └── predict.py           # POST /predict
│   │   ├── models/
│   │   │   ├── clip_model.py        # Wrapper del modelo CLIP
│   │   │   └── difficulty.py        # Lógica de dificultad
│   │   └── data/
│   │       ├── paintings.json       # Base de datos de cuadros
│   │       └── embeddings.npy       # Embeddings pre-calculados
│   ├── scripts/
│   │   ├── fetch_met_museum.py      # Descarga cuadros del Met Museum
│   │   ├── precompute_embeddings.py # Calcula embeddings (1 sola vez)
│   │   └── validate_db.py           # Valida paintings.json
│   └── requirements.txt
│
├── mobile/
│   ├── app/
│   │   ├── (tabs)/
│   │   │   ├── camara.tsx           # Pantalla cámara
│   │   │   ├── quiz.tsx             # Pantalla quiz
│   │   │   └── historial.tsx        # Historial de partidas
│   │   └── _layout.tsx
│   ├── components/
│   │   ├── TarjetaCuadro.tsx        # Tarjeta con resultado
│   │   ├── NivelDificultad.tsx      # Badge fácil/medio/difícil
│   │   └── BarraConfianza.tsx       # Barra de porcentaje
│   ├── services/
│   │   └── api.ts                   # Llamadas al backend
│   └── package.json
│
└── data-pipeline/
    ├── fetch_wikiart.py             # Scraping WikiArt (fase 2)
    └── normalize_metadata.py        # Normaliza datos de distintas fuentes
```

---

## Sistema de dificultad

| Nivel | Confidence del modelo | Comportamiento |
|-------|-----------------------|----------------|
| Fácil | 80%+ | 4 opciones, 1 correcta obvia |
| Medio | 50–80% | 4 opciones similares |
| Difícil | <50% | Solo escribe el autor (sin pistas) |

---

## Schema de paintings.json

```json
{
  "paintings": [
    {
      "id": "starry-night-van-gogh",
      "titulo": "La Noche Estrellada",
      "titulo_original": "The Starry Night",
      "artista": "Vincent van Gogh",
      "anio": 1889,
      "movimiento": "Post-Impresionismo",
      "museo": "MoMA, Nueva York",
      "image_url": "https://...",
      "embedding_index": 0,
      "tags": ["noche", "cielo", "pueblo"]
    }
  ]
}
```

---

## API Endpoints

### `POST /predict`

**Request:**
```json
{
  "image": "base64...",
  "top_k": 3
}
```

**Response:**
```json
{
  "resultado_principal": {
    "confianza": 0.91,
    "cuadro": { "...metadata..." },
    "dificultad": "facil"
  },
  "quiz": {
    "dificultad": "facil",
    "opciones_incorrectas": [
      { "artista": "Claude Monet", "titulo": "Nenúfares" },
      { "artista": "Pablo Picasso", "titulo": "Guernica" },
      { "artista": "Salvador Dalí", "titulo": "La Persistencia de la Memoria" }
    ]
  }
}
```

---

## Próximos pasos (en orden)

- [ ] Ejecutar `fetch_met_museum.py` y revisar los datos descargados
- [ ] Ejecutar `precompute_embeddings.py`
- [ ] Probar `/predict` con una imagen desde Swagger
- [ ] Conectar el móvil al backend local
- [ ] Diseño visual (pantallas, colores, tipografía)
- [ ] Deploy backend a Railway o Render
