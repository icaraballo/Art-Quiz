// ⚠️ En desarrollo: edita mobile/.env y cambia EXPO_PUBLIC_API_URL con tu IP actual
// ⚠️ En producción: apunta a la URL de Railway/Render
const BASE_URL = process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(public readonly status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function fetchConTimeout(
  url: string,
  options: RequestInit = {},
  ms = 10_000,
): Promise<Response> {
  const ctrl = new AbortController();
  const id = setTimeout(() => ctrl.abort(), ms);
  try {
    return await fetch(url, { ...options, signal: ctrl.signal });
  } finally {
    clearTimeout(id);
  }
}

export function imagenUrl(wikimediaUrl: string): string {
  return `${BASE_URL}/quiz/imagen?url=${encodeURIComponent(wikimediaUrl)}`;
}

export interface Pregunta {
  session_id: string;
  nivel: number;
  cuadro: {
    id: string;
    image_url: string;
    titulo_display: string | null;   // null cuando el campo preguntado ES el título
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
  const res = await fetchConTimeout(url);
  if (!res.ok) throw new ApiError(res.status, `Error ${res.status}`);
  return res.json();
}

export async function enviarRespuesta(
  sessionId: string,
  cuadroId: string,
  campo: string,
  respuesta: string,
  timeout = false,
): Promise<RespuestaResult> {
  const res = await fetchConTimeout(
    `${BASE_URL}/quiz/respuesta`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, cuadro_id: cuadroId, campo, respuesta, timeout }),
    },
  );
  if (!res.ok) throw new ApiError(res.status, `Error ${res.status}`);
  return res.json();
}

export async function obtenerProgreso(sessionId: string): Promise<Progreso> {
  const res = await fetchConTimeout(
    `${BASE_URL}/quiz/progreso?session_id=${encodeURIComponent(sessionId)}`,
  );
  if (!res.ok) throw new ApiError(res.status, `Error ${res.status}`);
  return res.json();
}
