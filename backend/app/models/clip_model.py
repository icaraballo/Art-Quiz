"""
Wrapper del modelo CLIP para reconocimiento de cuadros.

La primera vez que se instancia carga el modelo (~400MB).
Los embeddings de los cuadros se pre-calculan con scripts/precompute_embeddings.py
y se guardan en data/embeddings.npy para que las consultas sean rápidas (~200ms).
"""

from pathlib import Path
from typing import List, Optional

import numpy as np
from PIL import Image

EMBEDDINGS_PATH = Path(__file__).parent.parent / "data" / "embeddings.npy"


class ModeloCLIP:
    def __init__(self):
        self._modelo = None
        self._preprocesador = None
        self._embeddings_cuadros: Optional[np.ndarray] = None

    def _cargar(self):
        """Carga el modelo solo cuando se necesita por primera vez."""
        if self._modelo is not None:
            return

        print("⏳ Cargando modelo CLIP (primera vez, puede tardar 30s)...")
        import open_clip
        import torch

        self._modelo, _, self._preprocesador = open_clip.create_model_and_transforms(
            "ViT-B-32", pretrained="openai"
        )
        self._modelo.eval()
        print("✅ Modelo CLIP cargado")

    def _cargar_embeddings(self):
        """Carga los embeddings pre-calculados de los cuadros."""
        if self._embeddings_cuadros is not None:
            return True

        if not EMBEDDINGS_PATH.exists():
            print("⚠️  No se encontraron embeddings. Ejecuta scripts/precompute_embeddings.py")
            return False

        self._embeddings_cuadros = np.load(str(EMBEDDINGS_PATH))
        print(f"✅ Embeddings cargados: {self._embeddings_cuadros.shape[0]} cuadros")
        return True

    def predecir(self, imagen: Image.Image, paintings: list, top_k: int = 3) -> List[dict]:
        """
        Dado una imagen PIL, devuelve los top_k cuadros más similares
        con su confianza (cosine similarity).
        """
        self._cargar()

        if not self._cargar_embeddings():
            # Fallback: devolver cuadros aleatorios con baja confianza
            import random
            seleccionados = random.sample(paintings, min(top_k, len(paintings)))
            return [{"confianza": 0.1, "cuadro": p} for p in seleccionados]

        import torch

        # Calcular embedding de la imagen de entrada
        imagen_tensor = self._preprocesador(imagen).unsqueeze(0)
        with torch.no_grad():
            embedding_query = self._modelo.encode_image(imagen_tensor)
            embedding_query = embedding_query / embedding_query.norm(dim=-1, keepdim=True)
            embedding_query = embedding_query.numpy().flatten()

        # Cosine similarity contra todos los embeddings pre-calculados
        embeddings_norm = self._embeddings_cuadros / np.linalg.norm(
            self._embeddings_cuadros, axis=1, keepdims=True
        )
        similitudes = embeddings_norm @ embedding_query

        # Top-k índices
        indices_top = np.argsort(similitudes)[::-1][:top_k]

        resultados = []
        for idx in indices_top:
            if idx < len(paintings):
                resultados.append({
                    "confianza": float(similitudes[idx]),
                    "cuadro": paintings[idx]
                })

        return resultados


# Instancia global (singleton)
modelo_clip = ModeloCLIP()
