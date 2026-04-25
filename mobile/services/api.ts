// ⚠️ Cambia esta IP por la de tu Mac: Ajustes → WiFi → detalles de red
const BASE_URL = "http://192.168.1.100:8000";

export interface Pregunta {
  session_id: string;
  nivel: number;
  cuadro: {
    id: string;
    image_url: string;
    titulo_display: string;
  };
  pregunta: string;
  campo: string;
  modo: "test" | "libre";
  opciones: string[] | null;
  ya_visto: boolean;
}

export interface RespuestaResult {
  correcto: boolean;
  respuesta_correcta: string;
  titulo_original: string;
  titulo: string;
  artista: string;
  nivel_anterior: number;
  nivel_nuevo: number;
  racha: number;
}

export interface Progreso {
  session_id: string;
  nivel: number;
  total_preguntas: number;
  total_aciertos: number;
  porcentaje: number;
  racha_actual: number;
}

export async function obtenerPregunta(sessionId?: string): Promise<Pregunta> {
  const url = sessionId
    ? `${BASE_URL}/quiz/pregunta?session_id=${encodeURIComponent(sessionId)}`
    : `${BASE_URL}/quiz/pregunta`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Error ${res.status}`);
  return res.json();
}

export async function enviarRespuesta(
  sessionId: string,
  cuadroId: string,
  campo: string,
  respuesta: string,
): Promise<RespuestaResult> {
  const res = await fetch(`${BASE_URL}/quiz/respuesta`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, cuadro_id: cuadroId, campo, respuesta }),
  });
  if (!res.ok) throw new Error(`Error ${res.status}`);
  return res.json();
}

export async function obtenerProgreso(sessionId: string): Promise<Progreso> {
  const res = await fetch(`${BASE_URL}/quiz/progreso?session_id=${encodeURIComponent(sessionId)}`);
  if (!res.ok) throw new Error(`Error ${res.status}`);
  return res.json();
}

export async function verificarConexion(): Promise<boolean> {
  try {
    const res = await fetch(`${BASE_URL}/salud`, { method: "GET" });
    return res.ok;
  } catch {
    return false;
  }
}
