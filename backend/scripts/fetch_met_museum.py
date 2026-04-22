"""
Descarga pinturas de dominio público del Art Institute of Chicago (ARTIC).

API gratuita, sin autenticación, >1700 pinturas con imagen y metadatos completos.
Documentación: https://api.artic.edu/docs/

Uso:
    python scripts/fetch_met_museum.py
    python scripts/fetch_met_museum.py --limite 100   (para pruebas rápidas)

Genera: backend/app/data/paintings.json
"""

import argparse
import json
import re
import time
from pathlib import Path

import requests
from tqdm import tqdm

ARTIC_API = "https://api.artic.edu/api/v1"
ARTIC_IMAGE = "https://www.artic.edu/iiif/2/{image_id}/full/600,/0/default.jpg"
OUTPUT_PATH = Path(__file__).parent.parent / "app" / "data" / "paintings.json"

FIELDS = ",".join([
    "id", "title", "artist_display", "date_end", "date_display",
    "style_title", "place_of_origin", "image_id", "department_title",
    "is_public_domain", "artwork_type_title",
])
HEADERS = {"User-Agent": "ArtQuizApp/1.0 (educational project)"}


def slugify(texto: str) -> str:
    texto = texto.lower().strip()
    texto = re.sub(r"[^\w\s-]", "", texto)
    texto = re.sub(r"[\s_-]+", "-", texto)
    return texto[:60]


def extraer_artista(artist_display: str) -> str:
    """'Vincent van Gogh\nDutch, 1853–1890' → 'Vincent van Gogh'"""
    return (artist_display or "").split("\n")[0].strip()


def es_valida(obra: dict) -> bool:
    if not obra.get("image_id"):
        return False
    if not obra.get("is_public_domain"):
        return False
    if obra.get("artwork_type_title") != "Painting":
        return False
    if not obra.get("title"):
        return False
    if not extraer_artista(obra.get("artist_display", "")):
        return False
    return True


def normalizar(obra: dict, indice: int) -> dict:
    artista = extraer_artista(obra.get("artist_display", ""))
    titulo = obra.get("title", "Sin título")
    image_id = obra["image_id"]

    return {
        "id": slugify(f"{titulo}-{artista}"),
        "titulo": titulo,
        "titulo_original": titulo,
        "artista": artista,
        "anio": obra.get("date_end") or 0,
        "anio_display": obra.get("date_display", ""),
        "movimiento": obra.get("style_title") or obra.get("department_title") or "Desconocido",
        "museo": "Art Institute of Chicago",
        "lugar_origen": obra.get("place_of_origin", ""),
        "image_url": ARTIC_IMAGE.format(image_id=image_id),
        "image_url_grande": ARTIC_IMAGE.format(image_id=image_id).replace("600,", "1200,"),
        "artic_id": obra.get("id"),
        "embedding_index": indice,
        "tags": [],
        "departamento": obra.get("department_title", ""),
    }


def main(limite: int = 500):
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    cuadros = []
    page = 1
    per_page = 100
    total_paginas = None

    print(f"🎨 Descargando pinturas del Art Institute of Chicago (objetivo: {limite})...")

    with tqdm(total=limite, unit="cuadro") as pbar:
        while len(cuadros) < limite:
            params = {
                "fields": FIELDS,
                "limit": per_page,
                "page": page,
            }
            try:
                resp = requests.get(f"{ARTIC_API}/artworks", params=params,
                                    headers=HEADERS, timeout=30)
                resp.raise_for_status()
            except Exception as e:
                print(f"\n⚠️  Error en página {page}: {e}")
                time.sleep(2)
                continue

            data = resp.json()
            pag = data["pagination"]

            if total_paginas is None:
                total_paginas = pag["total_pages"]
                print(f"   Total de obras en la colección: {pag['total']} ({total_paginas} páginas)")

            for obra in data["data"]:
                if es_valida(obra):
                    cuadro = normalizar(obra, len(cuadros))
                    cuadros.append(cuadro)
                    pbar.update(1)
                    if len(cuadros) >= limite:
                        break

            if page >= total_paginas:
                print(f"\n⚠️  Se agotaron las páginas con solo {len(cuadros)} cuadros válidos")
                break

            page += 1
            time.sleep(0.1)

    datos = {
        "paintings": cuadros,
        "total": len(cuadros),
        "fuente": "Art Institute of Chicago",
    }
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Guardados {len(cuadros)} cuadros en {OUTPUT_PATH}")
    if cuadros:
        p = cuadros[0]
        print(f"   Ejemplo: {p['titulo']} — {p['artista']} ({p['anio_display']})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Descarga pinturas del Art Institute of Chicago")
    parser.add_argument("--limite", type=int, default=500, help="Número máximo de cuadros")
    args = parser.parse_args()
    main(limite=args.limite)
