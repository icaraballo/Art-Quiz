"""
Valida paintings.json y muestra estadísticas.

Uso:
    python scripts/validate_db.py
"""

import json
from pathlib import Path
from collections import Counter

DATA_PATH = Path(__file__).parent.parent / "app" / "data" / "paintings.json"
EMBEDDINGS_PATH = Path(__file__).parent.parent / "app" / "data" / "embeddings.npy"


def main():
    if not DATA_PATH.exists():
        print("❌ paintings.json no encontrado")
        return

    with open(DATA_PATH, "r", encoding="utf-8") as f:
        datos = json.load(f)

    paintings = datos.get("paintings", [])
    print(f"✅ Total cuadros: {len(paintings)}")

    # Comprobar campos obligatorios
    sin_imagen = [p for p in paintings if not p.get("image_url")]
    sin_artista = [p for p in paintings if not p.get("artista")]
    sin_titulo = [p for p in paintings if not p.get("titulo")]
    ids_duplicados = [id for id, count in Counter(p["id"] for p in paintings).items() if count > 1]

    print(f"\n📊 Calidad de datos:")
    print(f"   Sin imagen:    {len(sin_imagen)}")
    print(f"   Sin artista:   {len(sin_artista)}")
    print(f"   Sin título:    {len(sin_titulo)}")
    print(f"   IDs duplicados: {len(ids_duplicados)}")

    # Movimientos artísticos
    movimientos = Counter(p.get("movimiento", "Desconocido") for p in paintings)
    print(f"\n🎨 Top 10 movimientos:")
    for mov, count in movimientos.most_common(10):
        print(f"   {mov}: {count}")

    # Años
    anios = [p["anio"] for p in paintings if p.get("anio")]
    if anios:
        print(f"\n📅 Rango de años: {min(anios)} – {max(anios)}")

    # Embeddings
    if EMBEDDINGS_PATH.exists():
        import numpy as np
        emb = np.load(str(EMBEDDINGS_PATH))
        print(f"\n🔢 Embeddings: {emb.shape} ({'✅ coincide' if emb.shape[0] == len(paintings) else '⚠️ no coincide con paintings'})")
    else:
        print(f"\n⚠️  embeddings.npy no encontrado — ejecuta precompute_embeddings.py")

    print("\n🎯 Ejemplo de cuadro:")
    if paintings:
        p = paintings[0]
        print(f"   Título:    {p['titulo']}")
        print(f"   Artista:   {p['artista']}")
        print(f"   Año:       {p['anio']}")
        print(f"   Movimiento: {p['movimiento']}")
        print(f"   Imagen:    {p['image_url'][:60]}...")


if __name__ == "__main__":
    main()
