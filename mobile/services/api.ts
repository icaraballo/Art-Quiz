/**
 * Servicio de comunicación con el backend de Art Quiz.
 *
 * En desarrollo: apunta a tu Mac local.
 * En producción: cambia BASE_URL a la URL de Railway/Render.
 */

// ⚠️ Cambia esta IP por la IP de tu Mac en la red local
// La encuentras en: Ajustes del Mac → WiFi → detalles de la red
const BASE_URL = "http://192.168.1.100:8000";

export interface CuadroMetadata {
  id: string;
  titulo: string;
  artista: string;
  anio: number;
  movimiento: string;
  museo: string;
  image_url: string;
}

export interface ResultadoPrediccion {
  resultado_principal: {
    confianza: number;
    cuadro: CuadroMetadata;
    dificultad: "facil" | "medio" | "dificil";
  };
  quiz: {
    dificultad: "facil" | "medio" | "dificil";
    opciones_incorrectas: Array<{ artista: string; titulo: string }>;
  };
  total_cuadros_bd: number;
}

/**
 * Envía una imagen al backend y recibe la predicción.
 * @param imagenBase64 - Imagen codificada en base64 (sin el prefijo data:image/...)
 */
export async function predecirCuadro(imagenBase64: string): Promise<ResultadoPrediccion> {
  const response = await fetch(`${BASE_URL}/predict/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ image: imagenBase64, top_k: 3 }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || `Error del servidor: ${response.status}`);
  }

  return response.json();
}

/**
 * Comprueba si el servidor está disponible.
 */
export async function verificarConexion(): Promise<boolean> {
  try {
    const response = await fetch(`${BASE_URL}/salud`, { method: "GET" });
    return response.ok;
  } catch {
    return false;
  }
}
