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
SELECT ?painting ?image ?artist ?sitelinks WHERE {{
  ?painting wdt:P31 wd:Q3305213 ;
            wdt:P18 ?image ;
            wdt:P170 ?artist .
  ?artist wdt:P570 ?fechaMuerte .
  FILTER(YEAR(?fechaMuerte) < 1927)
  ?painting wikibase:sitelinks ?sitelinks .
}}
LIMIT {limit} OFFSET {offset}
"""

BATCH_SPARQL = 50
DELAY_SPARQL = 3.0

# QIDs de pinturas icónicas que deben estar siempre en el dataset
CURATED_QIDS: dict[str, str] = {
    "Q12418":   "Q762",    # Mona Lisa — Leonardo da Vinci
    "Q174":     "Q5593",   # Las Meninas — Velázquez
    "Q45585":   "Q5582",   # La noche estrellada — Van Gogh
    "Q151991":  "Q5679",   # La ronda de noche — Rembrandt
    "Q170571":  "Q39246",  # El nacimiento de Venus — Botticelli
    "Q131112":  "Q41406",  # La balsa de la Medusa — Géricault
    "Q214867":  "Q39718",  # El matrimonio Arnolfini — Van Eyck
    "Q154426":  "Q5582",   # Los girasoles — Van Gogh
    "Q46538":   "Q5592",   # La última cena — Leonardo da Vinci
    "Q173281":  "Q39259",  # La joven de la perla — Vermeer
    "Q3674":    "Q5599",   # Los fusilamientos del 3 de mayo — Goya
    "Q210804":  "Q39246",  # Primavera — Botticelli
    "Q3681":    "Q5593",   # Las hilanderas — Velázquez
    "Q193076":  "Q5582",   # La noche de café — Van Gogh
    "Q1141037": "Q762",    # La dama del armiño — Leonardo da Vinci
    "Q46538":   "Q5592",   # La última cena — Leonardo
    "Q182537":  "Q5597",   # Saturno devorando a su hijo — Goya
    "Q4765":    "Q41406",  # Liberty Leading the People — Delacroix
    "Q46735":   "Q41406",  # La muerte de Sardanápalo — Delacroix
    "Q191667":  "Q41531",  # Olympia — Manet
    "Q182564":  "Q41531",  # Le Déjeuner sur l'herbe — Manet
    "Q48584":   "Q36359",  # Impression, Sunrise — Monet
}


def _sparql_page(offset: int) -> list[dict]:
    q = SPARQL_PAGE.format(limit=BATCH_SPARQL, offset=offset)
    for intento in range(3):
        try:
            r = requests.get(
                SPARQL_ENDPOINT,
                params={"query": q, "format": "json"},
                headers=HEADERS,
                timeout=90,
            )
            r.raise_for_status()
            return r.json().get("results", {}).get("bindings", [])
        except Exception as e:
            espera = 15 * (intento + 1)
            if intento < 2:
                print(f"  SPARQL offset {offset}: {e} — reintentando en {espera}s...")
                time.sleep(espera)
            else:
                print(f"  SPARQL offset {offset}: {e} — descartando página")
    return []


def obtener_ids(objetivo: int) -> list[dict]:
    """Devuelve lista de {qid, image_raw, artist_qid, sitelinks} sin duplicados.
    Siempre incluye los QIDs del curated list."""
    print(f"Paso 1: obteniendo QIDs de Wikidata (objetivo ~{objetivo})...")
    resultados: list[dict] = []
    qids_vistos: set[str] = set()

    # Incluir curated QIDs primero (con sitelinks alto garantizado)
    for qid, artist_qid in CURATED_QIDS.items():
        if qid not in qids_vistos:
            qids_vistos.add(qid)
            resultados.append({"qid": qid, "image_raw": "", "artist_qid": artist_qid, "sitelinks": 200})
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
                    sl = int(row.get("sitelinks", {}).get("value", 0) or 0)
                    resultados.append({"qid": qid, "image_raw": img, "artist_qid": art, "sitelinks": sl})
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
                "props": "labels|claims|sitelinks",
                "sitefilter": "eswiki",
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


def _claim_qids_all(entity: dict, prop: str) -> list[str]:
    """Devuelve todos los QIDs de una propiedad multivalor (p.ej. P186)."""
    result = []
    for c in entity.get("claims", {}).get(prop, []):
        snak = c.get("mainsnak", {})
        if snak.get("snaktype") != "value":
            continue
        dv = snak.get("datavalue", {})
        if dv.get("type") == "wikibase-entityid":
            nid = dv.get("value", {}).get("numeric-id", "")
            if nid:
                result.append(f"Q{nid}")
    return result


_RE_DISAMBIG = re.compile(r"\s*\([^)]+\)\s*$")


def _titulo_es(entity: dict) -> str:
    """Título en español: sitelink eswiki (Wikipedia ES) > label es."""
    sl = entity.get("sitelinks", {}).get("eswiki", {})
    title = sl.get("title", "")
    if title:
        return _RE_DISAMBIG.sub("", title).strip()
    v = entity.get("labels", {}).get("es")
    if v:
        return v["value"] if isinstance(v, dict) else str(v)
    return ""


def _titulo_en(entity: dict) -> str:
    """Título en inglés u original (label en)."""
    v = entity.get("labels", {}).get("en")
    if v:
        return v["value"] if isinstance(v, dict) else str(v)
    return ""


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

    # Recoger QIDs de museos (P195), movimientos (P135), materiales (P186)
    extra_qids: set[str] = set()
    for qid, ent in p_ents.items():
        m = _claim_qid(ent, "P195") or _claim_qid(ent, "P276")
        if m:
            extra_qids.add(m)
        mv = _claim_qid(ent, "P135")
        if mv:
            extra_qids.add(mv)
        for mat in _claim_qids_all(ent, "P186"):
            extra_qids.add(mat)
    # Movimientos del artista como fallback (P135 en la entidad del artista)
    for a_ent in a_ents.values():
        mv = _claim_qid(a_ent, "P135")
        if mv:
            extra_qids.add(mv)

    extra_list = list(extra_qids)
    print(f"  Descargando {len(extra_list)} museos/movimientos/materiales...")
    ex_ents: dict[str, dict] = {}
    for i in tqdm(range(0, len(extra_list), BATCH_API), desc="  extras", unit="batch"):
        chunk = extra_list[i: i + BATCH_API]
        ex_ents.update(_wbget(chunk))
        time.sleep(DELAY_API)

    resultados: list[dict] = []
    for d in ids_data:
        ent        = p_ents.get(d["qid"], {})
        titulo_es  = _titulo_es(ent)
        titulo_en  = _titulo_en(ent)
        titulo     = titulo_es or titulo_en
        artista    = _label(a_ents.get(d["artist_qid"], {}))
        if not titulo or not artista:
            continue
        if re.match(r"^Q\d+$", titulo) or re.match(r"^Q\d+$", artista):
            continue

        anio    = _claim_year(ent)
        # Museo: P195 (colección) > P276 (ubicación)
        m_qid   = _claim_qid(ent, "P195") or _claim_qid(ent, "P276")
        museo   = _label(ex_ents.get(m_qid, {})) or "Museo desconocido"
        # Movimiento: primero de la pintura, luego del artista como fallback
        mv_qid = (_claim_qid(ent, "P135")
                  or _claim_qid(a_ents.get(d["artist_qid"], {}), "P135"))
        movimi  = _label(ex_ents.get(mv_qid, {})) or "Sin clasificar"
        img_fn  = _claim_image(ent) or d["image_raw"].split("/")[-1]
        mat_qids   = _claim_qids_all(ent, "P186")
        mat_labels = [_label(ex_ents.get(q, {})) for q in mat_qids]
        mat_labels = [l for l in mat_labels if l]

        resultados.append({
            "titulo":          titulo,
            "titulo_original": titulo_en or titulo,
            "artista":         artista,
            "anio":            anio,
            "museo":           museo,
            "movimiento":      movimi,
            "image_filename":  img_fn,
            "materiales":      mat_labels,
            "sitelinks":       d.get("sitelinks", 0),
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


# Materiales que son soporte (van en la segunda parte: "X sobre Y")
_SOPORTES = {
    "lienzo", "tabla", "madera", "cobre", "papel", "cartón", "marfil",
    "pared", "muro", "seda", "tela", "pergamino", "piedra", "yeso",
    "panel", "canvas", "wood", "copper", "paper",
}


def _combinar_tipo(materiales: list[str]) -> str:
    """Combina labels P186 en formato legible: 'Óleo sobre lienzo'."""
    clean = [l.strip() for l in materiales if l.strip()]
    if not clean:
        return "Pintura"
    medios    = [l for l in clean if l.lower() not in _SOPORTES]
    soportes  = [l for l in clean if l.lower() in _SOPORTES]
    partes    = medios[:1] + soportes[:1]
    if not partes:
        partes = clean[:2]
    if len(partes) == 1:
        return partes[0][0].upper() + partes[0][1:]
    medio   = partes[0][0].upper() + partes[0][1:]
    soporte = partes[1].lower()
    return f"{medio} sobre {soporte}"


def _popularidad(sitelinks: int) -> int:
    """1 (desconocida) a 5 (icónica) según número de sitelinks de Wikipedia."""
    if sitelinks >= 100: return 5
    if sitelinks >= 40:  return 4
    if sitelinks >= 15:  return 3
    if sitelinks >= 5:   return 2
    return 1


def _es_completa(p: dict) -> bool:
    return (
        p["museo"]      not in {"Museo desconocido", ""}
        and p["movimiento"] not in {"Sin clasificar", ""}
        and p["tipo"]       not in {"Pintura", ""}
    )


_RE_SALA = re.compile(
    r"^(Room|Salle|Sala|Raum|Zaal|Gallery|Galerie)\b",
    re.IGNORECASE,
)


def normalizar(raw: dict, ids_vistos: set[str]) -> dict | None:
    titulo          = raw.get("titulo", "").strip()
    titulo_original = raw.get("titulo_original", titulo).strip()
    artista         = raw.get("artista", "").strip()
    img_fn          = raw.get("image_filename", "")
    if not titulo or not artista or not img_fn:
        return None

    anio      = raw.get("anio")
    museo_raw = (raw.get("museo") or "").strip()
    # Si el museo apunta a una sala/habitación específica, usar valor genérico
    museo  = museo_raw if museo_raw and not _RE_SALA.match(museo_raw) else "Museo desconocido"
    movimi = (raw.get("movimiento") or "Sin clasificar").strip()
    movimi = movimi[0].upper() + movimi[1:] if movimi else movimi
    epoca  = calcular_epoca(anio)
    tipo       = _combinar_tipo(raw.get("materiales", []))
    sitelinks  = raw.get("sitelinks", 0)
    popularidad = _popularidad(sitelinks)

    base_id = slugify(f"{titulo}-{artista}")
    uid = base_id
    n   = 2
    while uid in ids_vistos:
        uid = f"{base_id}-{n}"
        n  += 1
    ids_vistos.add(uid)

    return {
        "id":              uid,
        "titulo":          titulo,
        "titulo_original": titulo_original or titulo,
        "artista":         artista,
        "anio":            anio or 0,
        "anio_display":    str(anio) if anio else "Desconocido",
        "movimiento":      movimi,
        "tipo":            tipo,
        "epoca":           epoca,
        "museo":           museo,
        "popularidad":     popularidad,
        "image_url":       commons_thumbnail(img_fn),
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
        ids_data = obtener_ids(objetivo=min(limite + 800, 3000))
        if not ids_data:
            print("Sin datos de SPARQL. Abortando.")
            return
        print("\nPaso 2: enriqueciendo con metadatos...")
        raw_list = enriquecer(ids_data)
        with open(RAW_PATH, "w", encoding="utf-8") as f:
            json.dump(raw_list, f, ensure_ascii=False, indent=2)
        print(f"Caché guardada en {RAW_PATH}")

    print(f"\nNormalizando (objetivo: {limite} completas)...")
    todas: list[dict] = []
    ids_vistos: set[str] = set()
    for raw in raw_list:
        p = normalizar(raw, ids_vistos)
        if p:
            todas.append(p)

    # Inferencia intra-dataset: propaga movimiento del artista a sus obras sin clasificar
    artista_mov: dict[str, str] = {}
    for p in todas:
        if p["movimiento"] != "Sin clasificar":
            artista_mov.setdefault(p["artista"], p["movimiento"])
    inferidos = 0
    for p in todas:
        if p["movimiento"] == "Sin clasificar" and p["artista"] in artista_mov:
            p["movimiento"] = artista_mov[p["artista"]]
            inferidos += 1
    if inferidos:
        print(f"  Movimiento inferido por artista (dataset): {inferidos} pinturas")

    # Priorizar pinturas con todos los campos completos
    completas   = [p for p in todas if _es_completa(p)]
    incompletas = [p for p in todas if not _es_completa(p)]
    paintings   = completas[:limite]
    if len(paintings) < limite:
        paintings += incompletas[:limite - len(paintings)]
    print(f"  Total procesadas: {len(todas)} | Completas: {len(completas)} | "
          f"Usadas: {len(paintings)} (incompletas relleno: {max(0, len(paintings)-len(completas))})")

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
