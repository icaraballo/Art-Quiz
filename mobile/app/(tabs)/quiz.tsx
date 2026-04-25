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
import { obtenerPregunta, enviarRespuesta, type Pregunta, type RespuestaResult } from "../../services/api";

type Fase = "inicio" | "cargando" | "pregunta" | "feedback";

const C = {
  fondo:       "#0d0d1a",
  superficie:  "#1a1a2e",
  tarjeta:     "#16213e",
  acento:      "#e94560",
  texto:       "#ffffff",
  suave:       "#8892a4",
  correcto:    "#4caf50",
  incorrecto:  "#e53935",
  dorado:      "#f0a500",
};

const NIVEL_MAX = 10;

export default function PantallaQuiz() {
  const [fase, setFase]             = useState<Fase>("inicio");
  const [pregunta, setPregunta]     = useState<Pregunta | null>(null);
  const [feedback, setFeedback]     = useState<RespuestaResult | null>(null);
  const [seleccionada, setSeleccionada] = useState<string | null>(null);
  const [textoLibre, setTextoLibre] = useState("");
  const [nivel, setNivel]           = useState(1);
  const [racha, setRacha]           = useState(0);

  // Animación fondo de inicio
  const animFondo  = useRef(new Animated.Value(0)).current;
  const animOpacity = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.loop(
      Animated.sequence([
        Animated.timing(animFondo, { toValue: 1, duration: 4000, useNativeDriver: false }),
        Animated.timing(animFondo, { toValue: 0, duration: 4000, useNativeDriver: false }),
      ])
    ).start();
    Animated.timing(animOpacity, { toValue: 1, duration: 900, useNativeDriver: true }).start();
  }, []);

  const bgColor = animFondo.interpolate({
    inputRange: [0, 1],
    outputRange: ["#0d0d1a", "#1a0a2e"],
  });

  // ── Lógica API ─────────────────────────────────────────────────────────────

  async function iniciarJuego() {
    setFase("cargando");
    try {
      const data = await obtenerPregunta();
      setPregunta(data);
      setNivel(data.nivel);
      setRacha(0);
      setFase("pregunta");
    } catch {
      Alert.alert("Sin conexión", "Comprueba que el servidor está encendido y la IP es correcta.");
      setFase("inicio");
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
      setFase("feedback");
    } catch {
      Alert.alert("Error", "No se pudo enviar la respuesta.");
    }
  }

  async function siguientePregunta() {
    if (!pregunta) return;
    setFase("cargando");
    setSeleccionada(null);
    setTextoLibre("");
    setFeedback(null);
    try {
      const data = await obtenerPregunta(pregunta.session_id);
      setPregunta(data);
      setNivel(data.nivel);
      setFase("pregunta");
    } catch {
      Alert.alert("Error", "No se pudo cargar la siguiente pregunta.");
      setFase("inicio");
    }
  }

  // ── Pantalla de inicio ─────────────────────────────────────────────────────

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

  // ── Pantalla de carga ──────────────────────────────────────────────────────

  if (fase === "cargando" || !pregunta) {
    return (
      <View style={[s.contenedorInicio, { backgroundColor: C.fondo }]}>
        <ActivityIndicator size="large" color={C.acento} />
      </View>
    );
  }

  // ── Pantalla de quiz ───────────────────────────────────────────────────────

  const esFeedback = fase === "feedback";
  const esLibre    = pregunta.modo === "libre";
  const esCorrectoFb = feedback?.correcto ?? false;

  return (
    <KeyboardAvoidingView
      style={s.contenedor}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
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
          {racha > 0 && (
            <Text style={s.rachaTexto}>🔥 {racha}</Text>
          )}
        </View>

        {/* IMAGEN */}
        <View style={s.imagenWrap}>
          <Image
            source={{ uri: pregunta.cuadro.image_url }}
            style={s.imagen}
            resizeMode="cover"
          />

          {/* Badge ya visto */}
          {pregunta.ya_visto && (
            <View style={s.yaVistoBadge}>
              <Text style={s.yaVistoTexto}>🔄 Ya visto</Text>
            </View>
          )}

          {/* Overlay de feedback sobre la imagen */}
          {esFeedback && (
            <View style={[s.feedbackOverlay, { backgroundColor: esCorrectoFb ? "rgba(76,175,80,0.88)" : "rgba(229,57,53,0.88)" }]}>
              <Text style={s.feedbackIcono}>{esCorrectoFb ? "✓" : "✗"}</Text>
              <Text style={s.feedbackTitulo}>{esCorrectoFb ? "¡Correcto!" : "Incorrecto"}</Text>
              {!esCorrectoFb && (
                <Text style={s.feedbackRespuesta}>{feedback?.respuesta_correcta}</Text>
              )}
            </View>
          )}
        </View>

        {/* PREGUNTA */}
        <Text style={s.preguntaTexto}>{pregunta.pregunta}</Text>

        {/* OPCIONES — modo test */}
        {!esLibre && pregunta.opciones && (
          <View style={s.opcionesWrap}>
            {pregunta.opciones.map((op) => {
              const esEsta      = seleccionada === op;
              const marcaVerde  = esFeedback && op === feedback?.respuesta_correcta;
              const marcaRoja   = esFeedback && esEsta && !esCorrectoFb;
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
        {esLibre && (
          <View style={s.libreWrap}>
            <TextInput
              style={[s.inputLibre, esFeedback && { opacity: 0.5 }]}
              value={textoLibre}
              onChangeText={setTextoLibre}
              placeholder="Escribe tu respuesta..."
              placeholderTextColor={C.suave}
              editable={!esFeedback}
              autoCapitalize="words"
              returnKeyType="done"
              onSubmitEditing={() => textoLibre.trim() && responder(textoLibre.trim())}
            />
            {!esFeedback && (
              <TouchableOpacity
                style={[s.botonConfirmar, !textoLibre.trim() && { opacity: 0.35 }]}
                onPress={() => textoLibre.trim() && responder(textoLibre.trim())}
                disabled={!textoLibre.trim()}
                activeOpacity={0.8}
              >
                <Text style={s.textoConfirmar}>Confirmar</Text>
              </TouchableOpacity>
            )}
            {esFeedback && !esCorrectoFb && (
              <Text style={s.libreRespuestaCorrecta}>
                Respuesta correcta: {feedback?.respuesta_correcta}
              </Text>
            )}
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
    </KeyboardAvoidingView>
  );
}

const s = StyleSheet.create({
  // ── Inicio ────────────────────────────────────────────────────────────────
  contenedorInicio: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
  },
  bloqueInicio: {
    alignItems: "center",
    paddingHorizontal: 40,
  },
  emojiInicio: { fontSize: 72, marginBottom: 16 },
  tituloInicio: {
    fontSize: 52,
    fontWeight: "800",
    color: C.texto,
    letterSpacing: 3,
    marginBottom: 10,
  },
  subtituloInicio: {
    fontSize: 18,
    color: C.suave,
    marginBottom: 56,
    textAlign: "center",
  },
  botonJugar: {
    backgroundColor: C.acento,
    paddingHorizontal: 72,
    paddingVertical: 20,
    borderRadius: 50,
    shadowColor: C.acento,
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.5,
    shadowRadius: 20,
    elevation: 10,
  },
  textoBotonJugar: {
    color: "#fff",
    fontSize: 22,
    fontWeight: "700",
    letterSpacing: 1,
  },

  // ── Quiz ──────────────────────────────────────────────────────────────────
  contenedor: { flex: 1, backgroundColor: C.fondo },
  scroll:     { paddingTop: Platform.OS === "ios" ? 60 : 40 },

  // Header
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: 20,
    marginBottom: 14,
  },
  nivelLabel: { color: C.texto, fontSize: 15, fontWeight: "700", marginBottom: 6 },
  barraFondo: {
    width: 160,
    height: 6,
    backgroundColor: C.tarjeta,
    borderRadius: 3,
    overflow: "hidden",
  },
  barraRelleno: {
    height: "100%",
    backgroundColor: C.acento,
    borderRadius: 3,
  },
  rachaTexto: { color: C.dorado, fontSize: 20, fontWeight: "700" },

  // Imagen
  imagenWrap: {
    marginHorizontal: 20,
    height: 230,
    borderRadius: 18,
    overflow: "hidden",
    backgroundColor: C.tarjeta,
    marginBottom: 20,
  },
  imagen: { width: "100%", height: "100%" },

  // Badge ya visto
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

  // Overlay feedback
  feedbackOverlay: {
    ...StyleSheet.absoluteFillObject,
    justifyContent: "center",
    alignItems: "center",
    gap: 4,
  },
  feedbackIcono:    { fontSize: 52, color: "#fff", fontWeight: "800" },
  feedbackTitulo:   { fontSize: 24, color: "#fff", fontWeight: "700" },
  feedbackRespuesta: {
    fontSize: 14,
    color: "rgba(255,255,255,0.92)",
    marginTop: 6,
    textAlign: "center",
    paddingHorizontal: 20,
  },

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
  opcionesWrap: { paddingHorizontal: 20, gap: 10 },
  opcion: {
    backgroundColor: C.tarjeta,
    borderRadius: 14,
    paddingVertical: 16,
    paddingHorizontal: 20,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  opcionCorrecta:  { backgroundColor: C.correcto },
  opcionIncorrecta: { backgroundColor: C.incorrecto },
  opcionTexto:     { color: C.texto, fontSize: 15 },
  opcionTextoMarcado: { fontWeight: "700" },
  opcionIcono:     { color: "#fff", fontSize: 16, fontWeight: "700" },

  // Libre
  libreWrap:  { paddingHorizontal: 20, gap: 12 },
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
  libreRespuestaCorrecta: {
    color: C.correcto,
    fontSize: 15,
    textAlign: "center",
    fontWeight: "600",
    marginTop: 4,
  },

  // Siguiente
  botonSiguiente: {
    marginHorizontal: 20,
    marginTop: 22,
    backgroundColor: C.superficie,
    borderRadius: 14,
    paddingVertical: 18,
    alignItems: "center",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.08)",
  },
  textoSiguiente: { color: C.texto, fontSize: 16, fontWeight: "600" },
});
