/**
 * Pantalla del Quiz
 *
 * TODO: recibir los datos de predicción desde la pantalla de cámara
 *       via navegación. Por ahora muestra un placeholder.
 */

import { StyleSheet, Text, View } from "react-native";

export default function PantallaQuiz() {
  return (
    <View style={estilos.contenedor}>
      <Text style={estilos.titulo}>🎮 Quiz</Text>
      <Text style={estilos.subtitulo}>
        Aquí aparecerá el quiz después de fotografiar un cuadro.
      </Text>
    </View>
  );
}

const estilos = StyleSheet.create({
  contenedor: { flex: 1, justifyContent: "center", alignItems: "center", padding: 24 },
  titulo: { fontSize: 32, marginBottom: 16 },
  subtitulo: { fontSize: 16, color: "#666", textAlign: "center" },
});
