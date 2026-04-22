"""
Pre-calcula los embeddings CLIP de todos los cuadros en paintings.json.

Este script se ejecuta UNA SOLA VEZ. Descarga las imágenes, calcula sus
embeddings y los guarda en embeddings.npy.

Luego el servidor hace cosine similarity en <10ms en vez de recalcular todo.

Uso:
    python scripts/precompute_embeddings.py

Genera: backend/app/data/embeddings.npy
"""

import json
import io
from pathlib import Path

import numpy as np
import requests
import torch
import open_clip
from PIL import Image
from tqdm import tqdm

DATA_PATH = Path(__file__).parent.parent / "app" / "data" / "paintings.json"
EMBEDDINGS_PATH = Path(__file__).parent.parent / "app" / "data" / "embeddings.npy"


def descargar_imagen(url: str) -> Image.Image | None:
    """Descarga una imagen desde una URL."""
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        return Image.open(io.BytesIO(resp.content)).convert("RGB")
    except Exception:
        return None


def main():
    # Cargar BD
    if not DATA_PATH.exists():
        print("❌ No se encontró paintings.json. Ejecuta primero fetch_met_museum.py")
        return

    with open(DATA_PATH, "r", encoding="utf-8") as f:
        datos = json.load(f)

    paintings = datos.get("paintings", [])
    print(f"📋 {len(paintings)} cuadros encontrados en la BD")

    # Cargar modelo CLIP
    print("⏳ Cargando modelo CLIP...")
    modelo, _, preprocesador = open_clip.create_model_and_transforms(
        "ViT-B-32", pretrained="openai"
    )
    modelo.eval()
    print("✅ Modelo cargado")

    # Calcular embeddings
    embeddings = []
    errores = 0

    print("\n🎨 Calculando embeddings...")
    for cuadro in tqdm(paintings):
        url = cuadro.get("image_url", "")
        if not url:
            embeddings.append(np.zeros(512))
            errores += 1
            continue

        imagen = descargar_imagen(url)
        if imagen is None:
            embeddings.append(np.zeros(512))
            errores += 1
            continue

        with torch.no_grad():
            tensor = preprocesador(imagen).unsqueeze(0)
            embedding = modelo.encode_image(tensor)
            embedding = embedding / embedding.norm(dim=-1, keepdim=True)
            embeddings.append(embedding.numpy().flatten())

    # Guardar
    matriz = np.array(embeddings, dtype=np.float32)
    np.save(str(EMBEDDINGS_PATH), matriz)

    print(f"\n✅ Embeddings guardados: {matriz.shape}")
    print(f"   Errores (imágenes no descargables): {errores}/{len(paintings)}")
    print(f"   Archivo: {EMBEDDINGS_PATH}")


if __name__ == "__main__":
    main()
