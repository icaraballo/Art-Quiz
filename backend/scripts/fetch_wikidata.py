"""
Descarga las pinturas más famosas de Wikidata (todos los museos del mundo).

Estrategia de dos pasos:
  1. SPARQL simple → obtiene QIDs de pinturas + URL de imagen
  2. wbgetentities API → obtiene labels (es/en) + museo + movimiento + fecha
     en batches de 50, sin timeouts

Uso:
    python scripts/fetch_wikidata.py              # descarga + procesa
    python scripts/fetch_wikidata.py --refrescar  # borra caché y re-descarga

Genera: backend/app/data/paintings.json
"""

import argparse
import hashlib
import json
import re
import time
import urllib.parse
from pathlib import Path

import requests
from tqdm import tqdm

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
OUTPUT_PATH = Path(__file__).parent.parent / "app" / "data" / "paintings.json"
RAW_PATH = Path(__file__).parent.parent / "app" / "data" / "_raw_wikidata.json"

HEADERS_SPARQL = {
    "User-Agent": "ArtQuizApp/1.0 (educational; https://github.com/icaraballo/Art-Quiz)",
    "Accept": "application/sparql-results+json",
}
HEADERS_API = {
    "User-Agent": "ArtQuizApp/1.0 (educational; https://github.com/icaraballo/Art-Quiz)",
}

# ---------------------------------------------------------------------------
# Paso 1: SPARQL — solo QID + imagen (query mínima, no da timeout)
# ---------------------------------------------------------------------------

SPARQL_IDS = """
SELECT ?painting ?image ?artist WHERE {{
  ?painting wdt:P31 wd:Q3305213 ;
            wdt:P18 ?image ;
            wdt:P170 ?artist .
  ?artist wdt:P570 ?fechaMuerte .
  FILTER(YEAR(?fechaMuerte) < 1926)
}}
LIMIT {limit} OFFSET {offset}
"""

BATCH_SPARQL = 200
DELAY_SPARQL = 2.0


def _sparql_page(offset: int) -> list[dict]:
    q = SPARQL_IDS.format(limit=BATCH_SPARQL, offset=offset)
    try:
        r = requests.get(
            SPARQL_ENDPOINT,
            params={"query": q, "format": "json"},
            headers=HEADERS_SPARQL,
            timeout=55,
        )
        r.raise_for_status()
        return r.json().get("results", {}).get("bindings", [])
    except Exception as e:
        print(f"  SPARQL error en offset {offset}: {e}")
        return []


def obtener_ids(objetivo: int) -> list[dict]:
    """Devuelve lista de {qid, image_url, artist_qid} sin duplicados."""
    print(f"Paso 1: obteniendo IDs de pinturas de Wikidata (objetivo ~{objetivo})...")
    resultados: list[dict] = []
    qids_vistos: set[str] = set()
    offset = 0

    with tqdm(total=objetivo, unit="id") as pbar:
        while len(resultados) < objetivo:
            rows = _sparql_page(offset)
            if not rows:
                break
            nuevos = 0
            for r in rows:
                qid = r.get("painting", {}).get("value", "").split("/")[-1]
                if qid and qid not in qids_vistos:
                    qids_vistos.add(qid)
                    resultados.append({
                        "qid": qid,
                        "image_raw": r.get("image", {}).get("value", ""),
                        "artist_qid": r.get("artist", {}).get("value", "").split("/")[-1],
                    })
                    nuevos += 1
            pbar.update(nuevos)
            offset += BATCH_SPARQL
            if len(rows) < BATCH_SPARQL:
                break
            time.sleep(DELAY_SPARQL)

    print(f"  IDs obtenidos: {len(resultados)}")
    return resultados


# ---------------------------------------------------------------------------
# Paso 2: wbgetentities — labels + propiedades en batches de 50
# ---------------------------------------------------------------------------

BATCH_API = 50
DELAY_API = 1.0


def _wbget(qids: list[str]) -> dict:
    """Llama wbgetentities para una lista de QIDs."""
    try:
        r = requests.get(
            WIKIDATA_API,
            params={
                "action": "wbgetentities",
                "ids": "|".join(qids),
                "languages": "es|en",
                "props": "labels|claims",
                "format": "json",
                "formatversion": "2",
            },
            headers=HEADERS_API,
            timeout=30,
        )
        r.raise_for_status()
        return r.json().get("entities", {})
    except Exception as e:
        print(f"  API error: {e}")
        return {}


def _label(entity: dict, lang_priority: list[str] = ("es", "en")) -> str:
    labels = entity.get("labels", {})
    for lang in lang_priority:
        if lang in labels:
            return labels[lang]["value"]
    return ""


def _claim_value(entity: dict, prop: str) -> str:
    """Primer valor de una propiedad tipo item o string."""
    claims = entity.get("claims", {}).get(prop, [])
    for c in claims:
        mv = c.get("mainsnak", {}).get("datavalue", {})
        t = mv.get("type", "")
        if t == "wikibase-entityid":
            return "Q" + str(mv.get("value", {}).get("numeric-id", ""))
        if t == "string":
            return mv.get("value", "")
        if t == "time":
            return mv.get("value", {}).get("time", "")
    return ""


def _year_from_time(time_str: str) -> int | None:
    m = re.search(r"[+-]?(\d{4})", time_str)
    if m:
        y = int(m.group(1))
        return y if y > 0 else None
    return None


def enriquecer(ids_data: list[dict]) -> list[dict]:
    """Añade labels y propiedades a cada entrada usando wbgetentities."""
    print(f"Paso 2: descargando detalles de {len(ids_data)} pinturas...")

    # Pre-cargamos todos los QIDs de pinturas y artistas juntos
    all_painting_qids = [d["qid"] for d in ids_data]
    all_artist_qids = list({d["artist_qid"] for d in ids_data if d["artist_qid"]})

    # Descargar entidades de pinturas
    painting_entities: dict[str, dict] = {}
    for i in tqdm(range(0, len(all_painting_qids), BATCH_API), desc="  pinturas", unit="batch"):
        chunk = all_painting_qids[i: i + BATCH_API]
        painting_entities.update(_wbget(chunk))
        time.sleep(DELAY_API)

    # Descargar entidades de artistas
    artist_entities: dict[str, dict] = {}
    for i in tqdm(range(0, len(all_artist_qids), BATCH_API), desc="  artistas", unit="batch"):
        chunk = all_artist_qids[i: i + BATCH_API]
        artist_entities.update(_wbget(chunk))
        time.sleep(DELAY_API)

    # Descargar labels de museos y movimientos (QIDs que aparecen en las pinturas)
    museum_qids: set[str] = set()
    movement_qids: set[str] = set()
    for qid, ent in painting_entities.items():
        m = _claim_value(ent, "P276")
        if m:
            museum_qids.add(m)
        mv = _claim_value(ent, "P135")
        if mv:
            movement_qids.add(mv)

    extra_qids = list(museum_qids | movement_qids)
    extra_entities: dict[str, dict] = {}
    for i in tqdm(range(0, len(extra_qids), BATCH_API), desc="  museos/mov.", unit="batch"):
        chunk = extra_qids[i: i + BATCH_API]
        extra_entities.update(_wbget(chunk))
        time.sleep(DELAY_API)

    # Combinar todo
    resultados = []
    for d in ids_data:
        ent = painting_entities.get(d["qid"], {})
        if not ent:
            continue

        artist_ent = artist_entities.get(d["artist_qid"], {})
        artista = _label(artist_ent) if artist_ent else ""
        if not artista:
            continue

        titulo = _label(ent)
        if not titulo or re.match(r"^Q\d+$", titulo):
            continue

        # Fecha
        fecha_str = _claim_value(ent, "P571")
        anio = _year_from_time(fecha_str) if fecha_str else None

        # Museo
        museo_qid = _claim_value(ent, "P276")
        museo_ent = extra_entities.get(museo_qid, {})
        museo = _label(museo_ent) if museo_ent else "Museo desconocido"

        # Movimiento
        mov_qid = _claim_value(ent, "P135")
        mov_ent = extra_entities.get(mov_qid, {})
        movimiento = _label(mov_ent) if mov_ent else "Sin clasificar"

        resultados.append({
            "qid": d["qid"],
            "titulo": titulo,
            "artista": artista,
            "anio": anio,
            "museo": museo,
            "movimiento": movimiento,
            "image_raw": d["image_raw"],
        })

    return resultados


# ---------------------------------------------------------------------------
# Imagen: Wikimedia Commons thumbnail
# ---------------------------------------------------------------------------

def commons_thumbnail(image_url: str, width: int = 600) -> str:
    try:
        filename = urllib.parse.unquote(image_url.split("/")[-1])
        filename = filename.replace(" ", "_")
        md5 = hashlib.md5(filename.encode("utf-8")).hexdigest()
        encoded = urllib.parse.quote(filename, safe="")
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        base = (
            f"https://upload.wikimedia.org/wikipedia/commons/thumb"
            f"/{md5[0]}/{md5[0:2]}/{encoded}/{width}px-{encoded}"
        )
        if ext == "svg":
            return base + ".png"
        if ext in ("tiff", "tif"):
            return base + ".jpg"
        return base
    except Exception:
        return image_url


# ---------------------------------------------------------------------------
# Normalización al schema final
# ---------------------------------------------------------------------------

def slugify(texto: str) -> str:
    texto = texto.lower().strip()
    for src, dst in [("á","a"),("à","a"),("ä","a"),("é","e"),("è","e"),("ë","e"),
                     ("í","i"),("ì","i"),("ï","i"),("ó","o"),("ò","o"),("ö","o"),
                     ("ú","u"),("ù","u"),("ü","u"),("ñ","n")]:
        texto = texto.replace(src, dst)
    texto = re.sub(r"[^\w\s-]", "", texto)
    texto = re.sub(r"[\s_-]+", "-", texto)
    return texto[:60].strip("-")


def calcular_epoca(anio: int | None) -> str:
    if not anio:
        return "Desconocida"
    if anio < 1400:
        return "Medieval"
    if anio < 1600:
        return "Renacimiento"
    if anio < 1700:
        return "Barroco"
    if anio < 1800:
        return "Siglo XVIII"
    if anio < 1850:
        return "Romanticismo"
    if anio < 1900:
        return "Siglo XIX"
    if anio < 1945:
        return "Primer Siglo XX"
    return "Arte Contemporáneo"


def normalizar(raw: dict, ids_vistos: set[str]) -> dict | None:
    titulo = raw.get("titulo", "").strip()
    artista = raw.get("artista", "").strip()
    if not titulo or not artista:
        return None

    anio = raw.get("anio")
    anio_display = str(anio) if anio else "Desconocido"
    museo = (raw.get("museo") or "Museo desconocido").strip()
    movimiento = (raw.get("movimiento") or "Sin clasificar").strip()
    # Capitalizar primera letra
    movimiento = movimiento[0].upper() + movimiento[1:] if movimiento else movimiento
    epoca = calcular_epoca(anio)
    image_url = commons_thumbnail(raw.get("image_raw", ""))

    base_id = slugify(f"{titulo}-{artista}")
    uid = base_id
    counter = 2
    while uid in ids_vistos:
        uid = f"{base_id}-{counter}"
        counter += 1
    ids_vistos.add(uid)

    return {
        "id": uid,
        "titulo": titulo,
        "titulo_original": titulo,
        "artista": artista,
        "anio": anio or 0,
        "anio_display": anio_display,
        "movimiento": movimiento,
        "tipo": "Pintura",
        "epoca": epoca,
        "museo": museo,
        "image_url": image_url,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(limite: int = 1000):
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    if RAW_PATH.exists():
        print(f"Usando caché {RAW_PATH}...")
        with open(RAW_PATH, encoding="utf-8") as f:
            raw_list = json.load(f)
    else:
        ids_data = obtener_ids(objetivo=min(limite + 300, 1500))
        if not ids_data:
            print("Sin datos. Abortando.")
            return
        raw_list = enriquecer(ids_data)
        with open(RAW_PATH, "w", encoding="utf-8") as f:
            json.dump(raw_list, f, ensure_ascii=False, indent=2)
        print(f"Caché guardada en {RAW_PATH}")

    print(f"\nNormalizando (objetivo: {limite})...")
    paintings: list[dict] = []
    ids_vistos: set[str] = set()

    for raw in raw_list:
        if len(paintings) >= limite:
            break
        p = normalizar(raw, ids_vistos)
        if p:
            paintings.append(p)

    datos = {
        "paintings": paintings,
        "total": len(paintings),
        "fuente": "Wikidata / Wikimedia Commons",
    }
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)

    museos: dict[str, int] = {}
    for p in paintings:
        museos[p["museo"]] = museos.get(p["museo"], 0) + 1

    print(f"\nGuardados {len(paintings)} cuadros en {OUTPUT_PATH}")
    print("Top museos:")
    for museo, n in sorted(museos.items(), key=lambda x: -x[1])[:10]:
        print(f"  {n:4d}  {museo}")
    if paintings:
        p = paintings[0]
        print(f"\nEjemplo: {p['titulo']} — {p['artista']} ({p['anio_display']}) | {p['museo']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limite", type=int, default=1000)
    parser.add_argument(
        "--refrescar",
        action="store_true",
        help="Ignora la caché y vuelve a descargar",
    )
    args = parser.parse_args()
    if args.refrescar and RAW_PATH.exists():
        RAW_PATH.unlink()
        print("Caché eliminada.")
    main(limite=args.limite)
