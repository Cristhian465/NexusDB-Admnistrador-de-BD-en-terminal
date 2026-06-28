"""
NexusVoice — Control por voz para Nexus-DB.

Capa de entrada/salida por voz que se monta SOBRE el motor existente:
    🎤 micrófono → STT (voz→texto) → pipeline ai_helper (texto→SQL)
        → executor (ya existente) → resumen hablado → 🔊 TTS (texto→voz)

No modifica conectores ni la lógica de ejecución: solo traduce voz a comandos
y narra el resultado. Las dependencias son opcionales; si no están instaladas,
el resto de la aplicación sigue funcionando con normalidad.
"""

# ── Dependencias opcionales (carga perezosa y tolerante a fallos) ───────────────
import os as _os

try:
    import speech_recognition as sr
    import pyttsx3
    _DEPS_OK = True
    _DEPS_ERROR = ""
except Exception as _e:          # pragma: no cover
    _DEPS_OK = False
    _DEPS_ERROR = str(_e)

# Vosk: reconocimiento de voz OFFLINE (opcional, respaldo sin internet)
try:
    import json as _json
    import vosk as _vosk
    _VOSK_OK = True
except Exception:
    _VOSK_OK = False

# Ruta del modelo Vosk en español (descargable). Configurable por entorno.
_VOSK_MODEL_PATH = _os.environ.get(
    "NEXUS_VOSK_MODEL",
    _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "models", "vosk-es"),
)


# Frases para terminar el modo voz
_PALABRAS_SALIR = (
    "salir", "detente", "detener", "para", "termina", "terminar",
    "apaga la voz", "modo texto", "adios", "adiós", "chao", "cerrar",
)

# Idiomas/etiquetas que delatan una voz en español dentro de SAPI5
_MARCAS_ES = ("es-", "spanish", "español", "espanol", "sabina", "helena", "laura")


class AsistenteVoz:
    """Encapsula reconocimiento de voz (STT) y síntesis de voz (TTS)."""

    def __init__(self):
        self.disponible = _DEPS_OK
        self.error_init = _DEPS_ERROR
        self._rec = None
        self._tts_voice_id = None

        # Motor de transcripción: "auto" (Google online, con respaldo Vosk offline),
        # "google" (solo online) o "vosk" (solo offline).
        self.motor = _os.environ.get("NEXUS_STT", "auto").lower()
        self._vosk_model = None   # se carga de forma perezosa

        if not _DEPS_OK:
            return

        try:
            self._rec = sr.Recognizer()
            self._rec.dynamic_energy_threshold = True
            self._rec.pause_threshold = 0.8
            self._detectar_voz_es()
        except Exception as e:
            self.disponible = False
            self.error_init = str(e)

    # ── Configuración del motor de transcripción ───────────────────────────────
    def vosk_disponible(self) -> bool:
        """True si la librería Vosk y el modelo en español están presentes."""
        return _VOSK_OK and _os.path.isdir(_VOSK_MODEL_PATH)

    def set_motor(self, motor: str) -> bool:
        """Cambia el motor de transcripción: 'auto' | 'google' | 'vosk'."""
        motor = (motor or "").lower().strip()
        if motor not in ("auto", "google", "vosk"):
            return False
        self.motor = motor
        return True

    def _cargar_vosk(self):
        """Carga el modelo Vosk en español la primera vez que se necesita."""
        if self._vosk_model is None and self.vosk_disponible():
            try:
                _vosk.SetLogLevel(-1)   # silenciar logs de Vosk
                self._vosk_model = _vosk.Model(_VOSK_MODEL_PATH)
            except Exception:
                self._vosk_model = None
        return self._vosk_model

    # ── Configuración de la voz en español ─────────────────────────────────────
    def _detectar_voz_es(self):
        """Busca una voz en español entre las instaladas (SAPI5 en Windows)."""
        try:
            eng = pyttsx3.init()
            for v in eng.getProperty("voices"):
                etiqueta = " ".join(
                    [str(v.id), str(getattr(v, "name", ""))]
                    + [str(x) for x in (getattr(v, "languages", []) or [])]
                ).lower()
                if any(m in etiqueta for m in _MARCAS_ES):
                    self._tts_voice_id = v.id
                    break
            eng.stop()
        except Exception:
            self._tts_voice_id = None

    # ── Síntesis de voz (texto → audio) ────────────────────────────────────────
    def hablar(self, texto: str):
        """Reproduce 'texto' en voz alta. Reinicia el motor en cada llamada para
        evitar el bug de pyttsx3 al reutilizar runAndWait() en Windows."""
        if not self.disponible or not texto:
            return
        try:
            eng = pyttsx3.init()
            if self._tts_voice_id:
                eng.setProperty("voice", self._tts_voice_id)
            eng.setProperty("rate", 178)     # ritmo de habla
            eng.setProperty("volume", 1.0)
            eng.say(texto)
            eng.runAndWait()
            try:
                eng.stop()
            except Exception:
                pass
        except Exception:
            pass     # nunca debe romper el flujo principal

    # ── Reconocimiento de voz (audio → texto) ──────────────────────────────────
    def escuchar(self, timeout: int = 7, phrase_time_limit: int = 9):
        """Captura del micrófono y transcribe a texto en español.

        Retorna (texto, error). 'texto' es None si hubo algún problema y 'error'
        contiene un mensaje legible para mostrar al usuario.
        """
        if not self.disponible:
            return None, "Las dependencias de voz no están instaladas."

        try:
            with sr.Microphone() as source:
                self._rec.adjust_for_ambient_noise(source, duration=0.4)
                audio = self._rec.listen(
                    source, timeout=timeout, phrase_time_limit=phrase_time_limit
                )
        except sr.WaitTimeoutError:
            return None, "No escuché nada (tiempo agotado)."
        except Exception as e:
            return None, f"Error al acceder al micrófono: {e}"

        return self._transcribir(audio)

    def _transcribir(self, audio):
        """Convierte audio a texto según el motor configurado, con respaldo."""
        # Modo solo offline
        if self.motor == "vosk":
            return self._transcribir_vosk(audio)

        # Modo online (google o auto): intentar Google primero
        try:
            texto = self._rec.recognize_google(audio, language="es-ES")
            return texto.strip(), None
        except sr.UnknownValueError:
            return None, "No entendí lo que dijiste."
        except sr.RequestError as e:
            # Sin internet: en modo 'auto', recurrir a Vosk si está disponible
            if self.motor == "auto" and self.vosk_disponible():
                return self._transcribir_vosk(audio)
            return None, f"Sin conexión con el servicio de transcripción: {e}"
        except Exception as e:
            return None, f"Error de transcripción: {e}"

    def _transcribir_vosk(self, audio):
        """Transcribe audio con Vosk (offline)."""
        modelo = self._cargar_vosk()
        if modelo is None:
            return None, (
                "Modelo de voz offline (Vosk) no disponible. "
                "Descárgalo o define NEXUS_VOSK_MODEL."
            )
        try:
            pcm = audio.get_raw_data(convert_rate=16000, convert_width=2)
            rec = _vosk.KaldiRecognizer(modelo, 16000)
            rec.AcceptWaveform(pcm)
            resultado = _json.loads(rec.FinalResult())
            texto = (resultado.get("text") or "").strip()
            if not texto:
                return None, "No entendí lo que dijiste (offline)."
            return texto, None
        except Exception as e:
            return None, f"Error de transcripción offline: {e}"


# ── Utilidades de alto nivel ────────────────────────────────────────────────────

def es_palabra_salir(texto: str) -> bool:
    """Indica si el texto reconocido pide terminar el modo voz."""
    t = (texto or "").strip().lower()
    return any(p in t for p in _PALABRAS_SALIR)


def resumir_resultado(data) -> str:
    """Construye un resumen hablado, en español, a partir del resultado de una
    consulta (mismo formato que usan los conectores: columns/rows/affected_rows)."""
    if not data:
        return "La consulta se ejecutó, pero no devolvió resultados."

    if isinstance(data, dict) and "affected_rows" in data:
        n = data["affected_rows"]
        return f"Listo. Se {'afectó' if n == 1 else 'afectaron'} {n} fila{'' if n == 1 else 's'}."

    cols = (data.get("columns") if isinstance(data, dict) else None) or []
    rows = (data.get("rows") if isinstance(data, dict) else None) or []

    if not rows:
        return "No encontré resultados."

    n = len(rows)
    resumen = f"Encontré {n} resultado{'' if n == 1 else 's'}."

    # Describir la primera fila (hasta 3 campos) para dar contexto.
    try:
        primera = rows[0]
        pares = []
        for col, val in list(zip(cols, primera))[:3]:
            if val is None or str(val) == "":
                continue
            pares.append(f"{col}: {val}")
        if pares:
            resumen += " El primero es " + ", ".join(pares) + "."
    except Exception:
        pass

    return resumen
