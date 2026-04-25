"""
Descarga pinturas de dominio público de Wikidata (todos los museos del mundo).

Estrategia — dos pasos sin timeouts:
  1. SPARQL con LIMIT 50 por página → obtiene QIDs + URL de imagen
  2. wbgetentities en batches de 50 → labels (es/en) + museo (P195)
     + movimiento (P135) + fecha (P571)

Uso:
    python scripts/fetch_wikidata.py              # descarga + procesa
    python scripts/fetch_wikidata.py --refrescar  # borra caché y re-descarga
    python scripts/fetch_wikidata.py --limite 500 # solo 500 cuadros

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
WIKIDATA_API    = "https://www.wikidata.org/w/api.php"
OUTPUT_PATH = Path(__file__).parent.parent / "app" / "data" / "paintings.json"
RAW_PATH    = Path(__file__).parent.parent / "app" / "data" / "_raw_wikidata.json"

HEADERS = {
    "User-Agent": "ArtQuizApp/1.0 (educational; https://github.com/icaraballo/Art-Quiz)",
    "Accept": "application/sparql-results+json",
}

# ---------------------------------------------------------------------------
# Paso 1: SPARQL — solo QID + imagen + artist_qid
# Batches de 50: ~25-30 s por página, sin timeout
# ---------------------------------------------------------------------------

SPARQL_PAGE = """
SELECT ?painting ?image ?artist WHERE {{
  ?painting wdt:P31 wd:Q3305213 ;
            wdt:P18 ?image ;
            wdt:P170 ?artist .
  ?artist wdt:P570 ?fechaMuerte .
  FILTER(YEAR(?fechaMuerte) < 1927)
}}
LIMIT {limit} OFFSET {offset}
"""

BATCH_SPARQL = 50
DELAY_SPARQL = 3.0


def _sparql_page(offset: int) -> list[dict]:
    q = SPARQL_PAGE.format(limit=BATCH_SPARQL, offset=offset)
    try:
        r = requests.get(
            SPARQL_ENDPOINT,
            params={"query": q, "format": "json"},
            headers=HEADERS,
            timeout=40,
        )
        r.raise_for_status()
        return r.json().get("results", {}).get("bindings", [])
    except Exception as e:
        print(f"  SPARQL offset {offset}: {e}")
        return []


def obtener_ids(objetivo: int) -> list[dict]:
    """Devuelve lista de {qid, image_raw, artist_qid} sin duplicados."""
    print(f"Paso 1: obteniendo QIDs de Wikidata (objetivo ~{objetivo})...")
    resultados: list[dict] = []
    qids_vistos: set[str] = set()
    offset = 0

    with tqdm(total=objetivo, unit="id") as pbar:
        while len(resultados) < objetivo:
            rows = _sparql_page(offset)
            if not rows:
                break
            nuevos = 0
            for row in rows:
                qid = row.get("painting", {}).get("value", "").split("/")[-1]
                img = row.get("image", {}).get("value", "")
                art = row.get("artist", {}).get("value", "").split("/")[-1]
                if qid and qid not in qids_vistos and img:
                    qids_vistos.add(qid)
                    resultados.append({"qid": qid, "image_raw": img, "artist_qid": art})
                    nuevos += 1
            pbar.update(nuevos)
            offset += BATCH_SPARQL
            if len(rows) < BATCH_SPARQL:
                break
            time.sleep(DELAY_SPARQL)

    print(f"  QIDs obtenidos: {len(resultados)}")
    return resultados


# ---------------------------------------------------------------------------
# Paso 2: wbgetentities — labels + P195 (colección/museo) + P135 + P571
# Batches de 50: ~2 s por batch, sin timeout
# ---------------------------------------------------------------------------

BATCH_API = 50
DELAY_API  = 1.0


def _wbget(qids: list[str]) -> dict:
    try:
        r = requests.get(
            WIKIDATA_API,
            params={
                "action": "wbgetentities",
                "ids": "|".join(qids),
                "languages": "es|en",
                "props": "labels|claims",
                "format": "json",
            },
            headers=HEADERS,
            timeout=25,
        )
        r.raise_for_status()
        return r.json().get("entities", {})
    except Exception as e:
        print(f"  API error: {e}")
        return {}


def _label(entity: dict) -> str:
    labels = entity.get("labels", {})
    for lang in ("es", "en"):
        v = labels.get(lang)
        if v:
            return v["value"] if isinstance(v, dict) else str(v)
    return ""


def _claim_qid(entity: dict, prop: str) -> str:
    for c in entity.get("claims", {}).get(prop, []):
        snak = c.get("mainsnak", {})
        if snak.get("snaktype") != "value":
            continue
        dv = snak.get("datavalue", {})
        if dv.get("type") == "wikibase-entityid":
            nid = dv.get("value", {}).get("numeric-id", "")
            if nid:
                return f"Q{nid}"
    return ""


def _claim_image(entity: dict) -> str:
    for c in entity.get("claims", {}).get("P18", []):
        snak = c.get("mainsnak", {})
        dv = snak.get("datavalue", {})
        if dv.get("type") == "string":
            return dv["value"]
    return ""


def _claim_year(entity: dict) -> int | None:
    for c in entity.get("claims", {}).get("P571", []):
        snak = c.get("mainsnak", {})
        if snak.get("snaktype") != "value":
            continue
        dv = snak.get("datavalue", {})
        if dv.get("type") == "time":
            t = dv["value"].get("time", "")
            m = re.search(r"[+-]?(\d{4})", t)
            if m:
                y = int(m.group(1))
                return y if y > 0 else None
    return None


def enriquecer(ids_data: list[dict]) -> list[dict]:
    painting_qids = [d["qid"] for d in ids_data]
    artist_qids   = list({d["artist_qid"] for d in ids_data if d["artist_qid"]})

    print(f"  Descargando {len(painting_qids)} pinturas...")
    p_ents: dict[str, dict] = {}
    for i in tqdm(range(0, len(painting_qids), BATCH_API), desc="  pinturas", unit="batch"):
        p_ents.update(_wbget(painting_qids[i: i + BATCH_API]))
        time.sleep(DELAY_API)

    print(f"  Descargando {len(artist_qids)} artistas...")
    a_ents: dict[str, dict] = {}
    for i in tqdm(range(0, len(artist_qids), BATCH_API), desc="  artistas", unit="batch"):
        a_ents.update(_wbget(artist_qids[i: i + BATCH_API]))
        time.sleep(DELAY_API)

    # Recoger QIDs de museos (P195 = colección) y movimientos (P135)
    extra_qids: set[str] = set()
    for qid, ent in p_ents.items():
        m = _claim_qid(ent, "P195") or _claim_qid(ent, "P276")
        if m:
            extra_qids.add(m)
        mv = _claim_qid(ent, "P135")
        if mv:
            extra_qids.add(mv)

    print(f"  Descargando {len(extra_qids)} museos/movimientos...")
    ex_ents: dict[str, dict] = {}
    for i in tqdm(range(0, len(list(extra_qids)), BATCH_API), desc="  extras", unit="batch"):
        chunk = list(extra_qids)[i: i + BATCH_API]
        ex_ents.update(_wbget(chunk))
        time.sleep(DELAY_API)

    resultados: list[dict] = []
    for d in ids_data:
        ent     = p_ents.get(d["qid"], {})
        titulo  = _label(ent)
        artista = _label(a_ents.get(d["artist_qid"], {}))
        if not titulo or not artista:
            continue
        if re.match(r"^Q\d+$", titulo) or re.match(r"^Q\d+$", artista):
            continue

        anio    = _claim_year(ent)
        # Museo: P195 (colección) > P276 (ubicación)
        m_qid   = _claim_qid(ent, "P195") or _claim_qid(ent, "P276")
        museo   = _label(ex_ents.get(m_qid, {})) or "Museo desconocido"
        mv_qid  = _claim_qid(ent, "P135")
        movimi  = _label(ex_ents.get(mv_qid, {})) or "Sin clasificar"
        img_fn  = _claim_image(ent) or d["image_raw"].split("/")[-1]

        resultados.append({
            "titulo":         titulo,
            "artista":        artista,
            "anio":           anio,
            "museo":          museo,
            "movimiento":     movimi,
            "image_filename": img_fn,
        })

    return resultados


# ---------------------------------------------------------------------------
# Imagen: Wikimedia Commons thumbnail
# ---------------------------------------------------------------------------

def commons_thumbnail(filename_or_url: str, width: int = 600) -> str:
    try:
        raw = filename_or_url.split("/")[-1]
        filename = urllib.parse.unquote(raw).replace(" ", "_")
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
        return filename_or_url


# ---------------------------------------------------------------------------
# Normalización al schema final (11 campos)
# ---------------------------------------------------------------------------

def slugify(texto: str) -> str:
    texto = texto.lower().strip()
    for s, d in [("á","a"),("à","a"),("ä","a"),("é","e"),("è","e"),("ë","e"),
                 ("í","i"),("ì","i"),("ï","i"),("ó","o"),("ò","o"),("ö","o"),
                 ("ú","u"),("ù","u"),("ü","u"),("ñ","n")]:
        texto = texto.replace(s, d)
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


_RE_SALA = re.compile(
    r"^(Room|Salle|Sala|Raum|Zaal|Gallery|Galerie)\b",
    re.IGNORECASE,
)


def normalizar(raw: dict, ids_vistos: set[str]) -> dict | None:
    titulo  = raw.get("titulo", "").strip()
    artista = raw.get("artista", "").strip()
    img_fn  = raw.get("image_filename", "")
    if not titulo or not artista or not img_fn:
        return None

    anio    = raw.get("anio")
    museo_raw = (raw.get("museo") or "").strip()
    # Si el museo apunta a una sala/habitación específica, usar valor genérico
    museo = museo_raw if museo_raw and not _RE_SALA.match(museo_raw) else "Museo desconocido"
    movimi  = (raw.get("movimiento") or "Sin clasificar").strip()
    movimi  = movimi[0].upper() + movimi[1:] if movimi else movimi
    epoca   = calcular_epoca(anio)

    base_id = slugify(f"{titulo}-{artista}")
    uid = base_id
    n   = 2
    while uid in ids_vistos:
        uid = f"{base_id}-{n}"
        n  += 1
    ids_vistos.add(uid)

    return {
        "id":             uid,
        "titulo":         titulo,
        "titulo_original": titulo,
        "artista":        artista,
        "anio":           anio or 0,
        "anio_display":   str(anio) if anio else "Desconocido",
        "movimiento":     movimi,
        "tipo":           "Pintura",
        "epoca":          epoca,
        "museo":          museo,
        "image_url":      commons_thumbnail(img_fn),
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
        ids_data = obtener_ids(objetivo=min(limite + 300, 2000))
        if not ids_data:
            print("Sin datos de SPARQL. Abortando.")
            return
        print("\nPaso 2: enriqueciendo con metadatos...")
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
    for k, v in sorted(museos.items(), key=lambda x: -x[1])[:12]:
        print(f"  {v:4d}  {k}")
    if paintings:
        ex = paintings[0]
        print(f"\nEjemplo: {ex['titulo']} — {ex['artista']} ({ex['anio_display']}) | {ex['museo']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limite",    type=int, default=1000)
    parser.add_argument("--refrescar", action="store_true",
                        help="Borra caché y re-descarga de Wikidata")
    args = parser.parse_args()
    if args.refrescar and RAW_PATH.exists():
        RAW_PATH.unlink()
        print("Caché eliminada.")
    main(limite=args.limite)
