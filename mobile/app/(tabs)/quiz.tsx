import React, { useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Animated,
  Image,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import {
  obtenerPregunta,
  enviarRespuesta,
  obtenerProgreso,
  type Pregunta,
  type RespuestaResult,
  type Progreso,
} from "../../services/api";

type Fase = "inicio" | "pregunta" | "feedback" | "resumen";

const C = {
  fondo:      "#0d0d1a",
  superficie: "#1a1a2e",
  tarjeta:    "#16213e",
  acento:     "#e94560",
  texto:      "#ffffff",
  suave:      "#8892a4",
  correcto:   "#4caf50",
  incorrecto: "#e53935",
  dorado:     "#f0a500",
};

const NIVEL_MAX = 10;

interface Stats {
  total: number;
  aciertos: number;
  nivelMax: number;
  rachaMax: number;
}

export default function PantallaQuiz() {
  const [fase, setFase]               = useState<Fase>("inicio");
  const [pregunta, setPregunta]       = useState<Pregunta | null>(null);
  const [feedback, setFeedback]       = useState<RespuestaResult | null>(null);
  const [seleccionada, setSeleccionada] = useState<string | null>(null);
  const [textoLibre, setTextoLibre]   = useState("");
  const [nivel, setNivel]             = useState(1);
  const [racha, setRacha]             = useState(0);
  const [stats, setStats]             = useState<Stats>({ total: 0, aciertos: 0, nivelMax: 1, rachaMax: 0 });
  const [progreso, setProgreso]       = useState<Progreso | null>(null);
  const [imageLoading, setImageLoading] = useState(true);

  // Level-up / level-down overlay
  const [cambioNivel, setCambioNivel] = useState<{ nuevo: number; subio: boolean } | null>(null);

  // Animaciones
  const animFondo   = useRef(new Animated.Value(0)).current;  // color fondo inicio
  const animOpacity = useRef(new Animated.Value(0)).current;  // fade-in inicio
  const animFade    = useRef(new Animated.Value(1)).current;  // fade entre preguntas
  const animNivel   = useRef(new Animated.Value(0)).current;  // overlay nivel

  useEffect(() => {
    Animated.loop(
      Animated.sequence([
        Animated.timing(animFondo, { toValue: 1, duration: 4000, useNativeDriver: false }),
        Animated.timing(animFondo, { toValue: 0, duration: 4000, useNativeDriver: false }),
      ])
    ).start();
    Animated.timing(animOpacity, { toValue: 1, duration: 900, useNativeDriver: true }).start();
  }, []);

  // Reset imageLoading cuando cambia el cuadro
  useEffect(() => {
    setImageLoading(true);
  }, [pregunta?.cuadro.id]);

  const bgColor = animFondo.interpolate({
    inputRange: [0, 1],
    outputRange: ["#0d0d1a", "#1a0a2e"],
  });

  // ── Helpers de animación ───────────────────────────────────────────────────

  function mostrarCambioNivel(nuevo: number, subio: boolean) {
    setCambioNivel({ nuevo, subio });
    animNivel.setValue(0);
    Animated.sequence([
      Animated.timing(animNivel, { toValue: 1, duration: 300, useNativeDriver: true }),
      Animated.delay(1400),
      Animated.timing(animNivel, { toValue: 0, duration: 300, useNativeDriver: true }),
    ]).start(() => setCambioNivel(null));
  }

  // ── Lógica API ─────────────────────────────────────────────────────────────

  async function iniciarJuego() {
    setStats({ total: 0, aciertos: 0, nivelMax: 1, rachaMax: 0 });
    setNivel(1);
    setRacha(0);
    animFade.setValue(1);
    try {
      const data = await obtenerPregunta();
      setPregunta(data);
      setNivel(data.nivel);
      setFase("pregunta");
    } catch {
      Alert.alert("Sin conexión", "Comprueba que el servidor está encendido y que la IP en api.ts es correcta.");
    }
  }

  async function responder(respuesta: string) {
    if (!pregunta || fase === "feedback") return;
    setSeleccionada(respuesta);
    try {
      const result = await enviarRespuesta(
        pregunta.session_id,
        pregunta.cuadro.id,
        pregunta.campo,
        respuesta,
      );
      setFeedback(result);
      setNivel(result.nivel_nuevo);
      setRacha(result.racha);

      // Actualizar stats locales
      setStats(prev => ({
        total:    prev.total + 1,
        aciertos: prev.aciertos + (result.correcto ? 1 : 0),
        nivelMax: Math.max(prev.nivelMax, result.nivel_nuevo),
        rachaMax: Math.max(prev.rachaMax, result.racha),
      }));

      // Mostrar overlay si cambió el nivel
      if (result.nivel_nuevo !== result.nivel_anterior) {
        mostrarCambioNivel(result.nivel_nuevo, result.nivel_nuevo > result.nivel_anterior);
      }

      setFase("feedback");
    } catch {
      Alert.alert("Error", "No se pudo enviar la respuesta.");
      setSeleccionada(null);
    }
  }

  async function siguientePregunta() {
    if (!pregunta) return;

    // Fetch mientras la pantalla sigue visible
    try {
      const data = await obtenerPregunta(pregunta.session_id);

      // Fade out → swap datos → fade in
      Animated.timing(animFade, { toValue: 0, duration: 180, useNativeDriver: true }).start(() => {
        setPregunta(data);
        setNivel(data.nivel);
        setSeleccionada(null);
        setTextoLibre("");
        setFeedback(null);
        setFase("pregunta");
        Animated.timing(animFade, { toValue: 1, duration: 280, useNativeDriver: true }).start();
      });
    } catch {
      Alert.alert("Error", "No se pudo cargar la siguiente pregunta.");
      setFase("inicio");
    }
  }

  async function terminar() {
    if (!pregunta) return;
    try {
      const p = await obtenerProgreso(pregunta.session_id);
      setProgreso(p);
    } catch {
      setProgreso(null);
    }
    setFase("resumen");
  }

  function jugarDeNuevo() {
    setPregunta(null);
    setFeedback(null);
    setSeleccionada(null);
    setTextoLibre("");
    setProgreso(null);
    setFase("inicio");
  }

  // ── RENDER: Inicio ─────────────────────────────────────────────────────────

  if (fase === "inicio") {
    return (
      <Animated.View style={[s.contenedorInicio, { backgroundColor: bgColor }]}>
        <Animated.View style={[s.bloqueInicio, { opacity: animOpacity }]}>
          <Text style={s.emojiInicio}>🎨</Text>
          <Text style={s.tituloInicio}>Art Quiz</Text>
          <Text style={s.subtituloInicio}>¿Cuánto sabes de arte?</Text>
          <TouchableOpacity style={s.botonJugar} onPress={iniciarJuego} activeOpacity={0.8}>
            <Text style={s.textoBotonJugar}>Jugar</Text>
          </TouchableOpacity>
        </Animated.View>
      </Animated.View>
    );
  }

  // ── RENDER: Resumen ────────────────────────────────────────────────────────

  if (fase === "resumen") {
    const p = progreso;
    const pct = stats.total > 0 ? Math.round((stats.aciertos / stats.total) * 100) : 0;
    return (
      <View style={[s.contenedorInicio, { backgroundColor: C.fondo }]}>
        <View style={s.resumenWrap}>
          <Text style={s.resumenEmoji}>🏛️</Text>
          <Text style={s.resumenTitulo}>Partida terminada</Text>

          <View style={s.resumenGrid}>
            <StatCard label="Preguntas" valor={String(p?.total_preguntas ?? stats.total)} />
            <StatCard label="Aciertos"  valor={`${p?.total_aciertos ?? stats.aciertos} (${p?.porcentaje ?? pct}%)`} />
            <StatCard label="Nivel máx" valor={String(stats.nivelMax)} />
            <StatCard label="Racha máx" valor={`${stats.rachaMax} 🔥`} />
          </View>

          <TouchableOpacity style={s.botonJugar} onPress={jugarDeNuevo} activeOpacity={0.8}>
            <Text style={s.textoBotonJugar}>Jugar de nuevo</Text>
          </TouchableOpacity>
        </View>
      </View>
    );
  }

  if (!pregunta) return null;

  // ── RENDER: Quiz ───────────────────────────────────────────────────────────

  const esFeedback  = fase === "feedback";
  const esLibre     = pregunta.modo === "libre";
  const esCorrectoFb = feedback?.correcto ?? false;

  return (
    <View style={{ flex: 1, backgroundColor: C.fondo }}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === "ios" ? "padding" : undefined}>
        <Animated.View style={{ flex: 1, opacity: animFade }}>
          <ScrollView
            contentContainerStyle={s.scroll}
            keyboardShouldPersistTaps="handled"
            showsVerticalScrollIndicator={false}
          >
            {/* HEADER */}
            <View style={s.header}>
              <View>
                <Text style={s.nivelLabel}>Nivel {nivel}</Text>
                <View style={s.barraFondo}>
                  <View style={[s.barraRelleno, { width: `${(nivel / NIVEL_MAX) * 100}%` }]} />
                </View>
              </View>
              <View style={s.headerRight}>
                {racha > 0 && <Text style={s.rachaTexto}>🔥 {racha}</Text>}
                <TouchableOpacity onPress={terminar} style={s.botonTerminar}>
                  <Text style={s.textoTerminar}>Salir</Text>
                </TouchableOpacity>
              </View>
            </View>

            {/* IMAGEN */}
            <View style={s.imagenWrap}>
              <Image
                source={{ uri: pregunta.cuadro.image_url }}
                style={s.imagen}
                resizeMode="cover"
                onLoadStart={() => setImageLoading(true)}
                onLoadEnd={() => setImageLoading(false)}
              />

              {/* Placeholder mientras carga */}
              {imageLoading && (
                <View style={s.imagenPlaceholder}>
                  <ActivityIndicator color={C.acento} size="large" />
                </View>
              )}

              {/* Badge ya visto */}
              {pregunta.ya_visto && (
                <View style={s.yaVistoBadge}>
                  <Text style={s.yaVistoTexto}>🔄 Ya visto</Text>
                </View>
              )}

              {/* Overlay feedback sobre imagen */}
              {esFeedback && (
                <View style={[s.feedbackOverlay, { backgroundColor: esCorrectoFb ? "rgba(76,175,80,0.88)" : "rgba(229,57,53,0.88)" }]}>
                  <Text style={s.feedbackIcono}>{esCorrectoFb ? "✓" : "✗"}</Text>
                  <Text style={s.feedbackTitulo}>{esCorrectoFb ? "¡Correcto!" : "Incorrecto"}</Text>
                </View>
              )}
            </View>

            {/* INFO DEL CUADRO (siempre visible en feedback) */}
            {esFeedback && feedback && (
              <View style={s.cuadroInfo}>
                <Text style={s.cuadroTitulo}>{feedback.titulo}</Text>
                <Text style={s.cuadroArtista}>{feedback.artista}</Text>
                {!esCorrectoFb && (
                  <View style={s.respuestaCorrectaWrap}>
                    <Text style={s.respuestaCorrectaLabel}>Respuesta correcta</Text>
                    <Text style={s.respuestaCorrectaValor}>{feedback.respuesta_correcta}</Text>
                  </View>
                )}
              </View>
            )}

            {/* PREGUNTA */}
            {!esFeedback && (
              <Text style={s.preguntaTexto}>{pregunta.pregunta}</Text>
            )}

            {/* OPCIONES — modo test */}
            {!esLibre && pregunta.opciones && (
              <View style={s.opcionesWrap}>
                {pregunta.opciones.map((op) => {
                  const marcaVerde = esFeedback && op === feedback?.respuesta_correcta;
                  const marcaRoja  = esFeedback && seleccionada === op && !esCorrectoFb;
                  return (
                    <TouchableOpacity
                      key={op}
                      style={[s.opcion, marcaVerde && s.opcionCorrecta, marcaRoja && s.opcionIncorrecta]}
                      onPress={() => !esFeedback && responder(op)}
                      activeOpacity={esFeedback ? 1 : 0.7}
                      disabled={esFeedback}
                    >
                      <Text style={[s.opcionTexto, (marcaVerde || marcaRoja) && s.opcionTextoMarcado]}>
                        {op}
                      </Text>
                      {marcaVerde && <Text style={s.opcionIcono}>✓</Text>}
                      {marcaRoja  && <Text style={s.opcionIcono}>✗</Text>}
                    </TouchableOpacity>
                  );
                })}
              </View>
            )}

            {/* INPUT — modo libre */}
            {esLibre && !esFeedback && (
              <View style={s.libreWrap}>
                <Text style={s.preguntaTexto}>{pregunta.pregunta}</Text>
                <TextInput
                  style={s.inputLibre}
                  value={textoLibre}
                  onChangeText={setTextoLibre}
                  placeholder="Escribe tu respuesta..."
                  placeholderTextColor={C.suave}
                  autoCapitalize="words"
                  returnKeyType="done"
                  onSubmitEditing={() => textoLibre.trim() && responder(textoLibre.trim())}
                />
                <TouchableOpacity
                  style={[s.botonConfirmar, !textoLibre.trim() && { opacity: 0.35 }]}
                  onPress={() => textoLibre.trim() && responder(textoLibre.trim())}
                  disabled={!textoLibre.trim()}
                  activeOpacity={0.8}
                >
                  <Text style={s.textoConfirmar}>Confirmar</Text>
                </TouchableOpacity>
              </View>
            )}

            {/* BOTÓN SIGUIENTE */}
            {esFeedback && (
              <TouchableOpacity style={s.botonSiguiente} onPress={siguientePregunta} activeOpacity={0.8}>
                <Text style={s.textoSiguiente}>Siguiente →</Text>
              </TouchableOpacity>
            )}

            <View style={{ height: 40 }} />
          </ScrollView>
        </Animated.View>
      </KeyboardAvoidingView>

      {/* OVERLAY CAMBIO DE NIVEL — encima de todo */}
      {cambioNivel && (
        <Animated.View style={[s.nivelOverlay, { opacity: animNivel }]}>
          <Text style={s.nivelOverlayEmoji}>{cambioNivel.subio ? "🎉" : "😅"}</Text>
          <Text style={s.nivelOverlayTitulo}>
            {cambioNivel.subio ? "¡Nivel " : "Nivel "}
            {cambioNivel.nuevo}
            {cambioNivel.subio ? "!" : ""}
          </Text>
          <Text style={s.nivelOverlaySub}>
            {cambioNivel.subio ? "¡Vas muy bien!" : "Sigue practicando"}
          </Text>
        </Animated.View>
      )}
    </View>
  );
}

// ── Componente auxiliar StatCard ───────────────────────────────────────────

function StatCard({ label, valor }: { label: string; valor: string }) {
  return (
    <View style={s.statCard}>
      <Text style={s.statValor}>{valor}</Text>
      <Text style={s.statLabel}>{label}</Text>
    </View>
  );
}

// ── Estilos ────────────────────────────────────────────────────────────────

const s = StyleSheet.create({
  // Inicio
  contenedorInicio: { flex: 1, justifyContent: "center", alignItems: "center" },
  bloqueInicio:     { alignItems: "center", paddingHorizontal: 40 },
  emojiInicio:      { fontSize: 72, marginBottom: 16 },
  tituloInicio:     { fontSize: 52, fontWeight: "800", color: C.texto, letterSpacing: 3, marginBottom: 10 },
  subtituloInicio:  { fontSize: 18, color: C.suave, marginBottom: 56, textAlign: "center" },
  botonJugar: {
    backgroundColor: C.acento,
    paddingHorizontal: 64,
    paddingVertical: 20,
    borderRadius: 50,
    shadowColor: C.acento,
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.5,
    shadowRadius: 20,
    elevation: 10,
  },
  textoBotonJugar: { color: "#fff", fontSize: 22, fontWeight: "700", letterSpacing: 1 },

  // Resumen
  resumenWrap:   { alignItems: "center", paddingHorizontal: 32 },
  resumenEmoji:  { fontSize: 64, marginBottom: 12 },
  resumenTitulo: { fontSize: 28, fontWeight: "800", color: C.texto, marginBottom: 32 },
  resumenGrid:   { width: "100%", flexDirection: "row", flexWrap: "wrap", gap: 12, marginBottom: 40 },
  statCard: {
    flex: 1,
    minWidth: "45%",
    backgroundColor: C.tarjeta,
    borderRadius: 16,
    padding: 20,
    alignItems: "center",
  },
  statValor: { color: C.texto,  fontSize: 22, fontWeight: "800", marginBottom: 4 },
  statLabel: { color: C.suave,  fontSize: 13 },

  // Quiz
  scroll:  { paddingTop: Platform.OS === "ios" ? 60 : 40 },

  // Header
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: 20,
    marginBottom: 14,
  },
  nivelLabel: { color: C.texto, fontSize: 15, fontWeight: "700", marginBottom: 6 },
  barraFondo: { width: 140, height: 6, backgroundColor: C.tarjeta, borderRadius: 3, overflow: "hidden" },
  barraRelleno: { height: "100%", backgroundColor: C.acento, borderRadius: 3 },
  headerRight:  { alignItems: "flex-end", gap: 6 },
  rachaTexto:   { color: C.dorado, fontSize: 20, fontWeight: "700" },
  botonTerminar: { paddingHorizontal: 12, paddingVertical: 4 },
  textoTerminar: { color: C.suave, fontSize: 13 },

  // Imagen
  imagenWrap: {
    marginHorizontal: 20,
    height: 220,
    borderRadius: 18,
    overflow: "hidden",
    backgroundColor: C.tarjeta,
    marginBottom: 16,
  },
  imagen: { width: "100%", height: "100%" },
  imagenPlaceholder: {
    ...StyleSheet.absoluteFillObject,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: C.tarjeta,
  },
  yaVistoBadge: {
    position: "absolute",
    top: 10,
    right: 10,
    backgroundColor: "rgba(0,0,0,0.65)",
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 20,
  },
  yaVistoTexto: { color: C.dorado, fontSize: 12, fontWeight: "600" },
  feedbackOverlay: {
    ...StyleSheet.absoluteFillObject,
    justifyContent: "center",
    alignItems: "center",
  },
  feedbackIcono:  { fontSize: 52, color: "#fff", fontWeight: "800" },
  feedbackTitulo: { fontSize: 24, color: "#fff", fontWeight: "700" },

  // Info cuadro (feedback)
  cuadroInfo: {
    marginHorizontal: 20,
    marginBottom: 14,
    padding: 16,
    backgroundColor: C.tarjeta,
    borderRadius: 14,
    gap: 4,
  },
  cuadroTitulo:  { color: C.texto,  fontSize: 16, fontWeight: "700" },
  cuadroArtista: { color: C.suave,  fontSize: 14 },
  respuestaCorrectaWrap: { marginTop: 10, paddingTop: 10, borderTopWidth: 1, borderTopColor: "rgba(255,255,255,0.07)" },
  respuestaCorrectaLabel: { color: C.suave, fontSize: 12, marginBottom: 2 },
  respuestaCorrectaValor: { color: C.correcto, fontSize: 15, fontWeight: "700" },

  // Pregunta
  preguntaTexto: {
    color: C.texto,
    fontSize: 18,
    fontWeight: "600",
    textAlign: "center",
    paddingHorizontal: 24,
    marginBottom: 18,
    lineHeight: 26,
  },

  // Opciones
  opcionesWrap:       { paddingHorizontal: 20, gap: 10 },
  opcion: {
    backgroundColor: C.tarjeta,
    borderRadius: 14,
    paddingVertical: 16,
    paddingHorizontal: 20,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  opcionCorrecta:     { backgroundColor: C.correcto },
  opcionIncorrecta:   { backgroundColor: C.incorrecto },
  opcionTexto:        { color: C.texto, fontSize: 15 },
  opcionTextoMarcado: { fontWeight: "700" },
  opcionIcono:        { color: "#fff", fontSize: 16, fontWeight: "700" },

  // Libre
  libreWrap:     { paddingHorizontal: 20, gap: 12 },
  inputLibre: {
    backgroundColor: C.tarjeta,
    borderRadius: 14,
    padding: 16,
    color: C.texto,
    fontSize: 16,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.08)",
  },
  botonConfirmar: {
    backgroundColor: C.acento,
    borderRadius: 14,
    paddingVertical: 16,
    alignItems: "center",
  },
  textoConfirmar: { color: "#fff", fontSize: 16, fontWeight: "700" },

  // Siguiente
  botonSiguiente: {
    marginHorizontal: 20,
    marginTop: 20,
    backgroundColor: C.superficie,
    borderRadius: 14,
    paddingVertical: 18,
    alignItems: "center",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.08)",
  },
  textoSiguiente: { color: C.texto, fontSize: 16, fontWeight: "600" },

  // Overlay nivel
  nivelOverlay: {
    ...StyleSheet.absoluteFillObject,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: "rgba(13,13,26,0.92)",
    gap: 8,
  },
  nivelOverlayEmoji:  { fontSize: 64 },
  nivelOverlayTitulo: { color: C.texto, fontSize: 36, fontWeight: "800" },
  nivelOverlaySub:    { color: C.suave, fontSize: 18 },
});
