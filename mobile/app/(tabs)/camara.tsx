import { CameraView, useCameraPermissions } from "expo-camera";
import * as ImagePicker from "expo-image-picker";
import { useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Button,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { predecirCuadro, type ResultadoPrediccion } from "../../services/api";

export default function PantallacamAra() {
  const [permiso, solicitarPermiso] = useCameraPermissions();
  const [cargando, setCargando] = useState(false);
  const camaraRef = useRef<CameraView>(null);

  if (!permiso) return <View />;

  if (!permiso.granted) {
    return (
      <View style={estilos.contenedor}>
        <Text style={estilos.texto}>Necesitamos acceso a la cámara</Text>
        <Button onPress={solicitarPermiso} title="Dar permiso" />
      </View>
    );
  }

  async function fotografiar() {
    if (!camaraRef.current) return;
    setCargando(true);
    try {
      const foto = await camaraRef.current.takePictureAsync({ base64: true, quality: 0.7 });
      if (foto?.base64) {
        await enviarImagen(foto.base64);
      }
    } catch (err) {
      Alert.alert("Error", "No se pudo tomar la foto");
    } finally {
      setCargando(false);
    }
  }

  async function seleccionarDeGaleria() {
    const resultado = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      base64: true,
      quality: 0.7,
    });
    if (!resultado.canceled && resultado.assets[0].base64) {
      setCargando(true);
      try {
        await enviarImagen(resultado.assets[0].base64);
      } finally {
        setCargando(false);
      }
    }
  }

  async function enviarImagen(base64: string) {
    // TODO: navegar a la pantalla de quiz con el resultado
    const resultado: ResultadoPrediccion = await predecirCuadro(base64);
    console.log("Resultado:", resultado);
    Alert.alert(
      `🎨 ${resultado.resultado_principal.cuadro.titulo}`,
      `${resultado.resultado_principal.cuadro.artista} (${resultado.resultado_principal.cuadro.anio})\nConfianza: ${(resultado.resultado_principal.confianza * 100).toFixed(0)}%`
    );
  }

  return (
    <View style={estilos.contenedor}>
      <CameraView style={estilos.camara} ref={camaraRef}>
        {cargando && (
          <View style={estilos.overlay}>
            <ActivityIndicator size="large" color="#fff" />
            <Text style={estilos.textoOverlay}>Analizando cuadro...</Text>
          </View>
        )}
      </CameraView>
      <View style={estilos.controles}>
        <TouchableOpacity style={estilos.botonGaleria} onPress={seleccionarDeGaleria}>
          <Text style={estilos.textoBoton}>📷 Galería</Text>
        </TouchableOpacity>
        <TouchableOpacity style={estilos.botonFoto} onPress={fotografiar} disabled={cargando}>
          <View style={estilos.circuloFoto} />
        </TouchableOpacity>
        <View style={{ width: 80 }} />
      </View>
    </View>
  );
}

const estilos = StyleSheet.create({
  contenedor: { flex: 1, backgroundColor: "#000" },
  camara: { flex: 1 },
  overlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(0,0,0,0.6)",
    justifyContent: "center",
    alignItems: "center",
  },
  textoOverlay: { color: "#fff", marginTop: 12, fontSize: 16 },
  controles: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    padding: 24,
    backgroundColor: "#111",
  },
  botonGaleria: { width: 80, alignItems: "center" },
  botonFoto: {
    width: 72,
    height: 72,
    borderRadius: 36,
    borderWidth: 4,
    borderColor: "#fff",
    justifyContent: "center",
    alignItems: "center",
  },
  circuloFoto: { width: 56, height: 56, borderRadius: 28, backgroundColor: "#fff" },
  texto: { color: "#fff", fontSize: 16, textAlign: "center", margin: 20 },
  textoBoton: { color: "#fff", fontSize: 14 },
});
