import threading
import queue
import logging
import warnings
from typing import Any, List, Optional, Dict

# ──────────────────────────────────────────────────────────────────────
# SILENCE comtypes DEBUG spam (pyttsx3 triggers COM debug output)
# ──────────────────────────────────────────────────────────────────────
logging.getLogger("comtypes").setLevel(logging.WARNING)
logging.getLogger("comtypes.client").setLevel(logging.WARNING)
logging.getLogger("comtypes.client._events").setLevel(logging.WARNING)

# Detect Android via Kivy — platform.system() returns 'Linux' on Android,
# so we must use Kivy's own platform detection.
try:
    from kivy.utils import platform as _kivy_platform  # pyre-ignore
    _IS_ANDROID = (_kivy_platform == 'android')
except Exception:
    _IS_ANDROID = False

# plyer TTS — used on Android
try:
    from plyer import tts as _plyer_tts  # type: ignore
    _PLYER_AVAILABLE = True
except Exception:
    _PLYER_AVAILABLE = False
    _plyer_tts = None  # type: ignore


class SpeechEngine:
    """Manages audio text-to-speech on a background thread to prevent UI freezing.

    Android : uses plyer (native Android TTS — no install needed)
    Desktop  : uses pyttsx3 on a persistent background thread
    """

    def __init__(self):
        self.voices: List[Any] = []
        self._speech_queue: queue.Queue = queue.Queue()
        self._worker_ready = False
        self._engine_alive = False

        if not _IS_ANDROID:
            # Desktop path — pyttsx3
            t = threading.Thread(
                target=self._speech_worker, daemon=True, name="SpeechWorker"
            )
            t.start()
            # Ask worker to populate the voices list
            self._speech_queue.put({'type': 'init_voices'})

    # ------------------------------------------------------------------
    # Desktop pyttsx3 worker
    # ------------------------------------------------------------------
    def _speech_worker(self):
        engine = None
        try:
            import pyttsx3  # type: ignore
            engine = pyttsx3.init()
            self._engine_alive = True
        except Exception as e:
            print(f"SpeechEngine: pyttsx3 unavailable on desktop: {e}")
            return

        self._worker_ready = True

        while True:
            try:
                msg = self._speech_queue.get()
                if msg is None:
                    break

                msg_type = msg.get('type')

                if msg_type == 'speak':
                    try:
                        engine.say(msg['text'])
                        engine.runAndWait()
                    except Exception as e:
                        print(f"SpeechEngine: speak error: {e}")
                        # Re-init engine on failure
                        try:
                            import pyttsx3  # type: ignore
                            engine = pyttsx3.init()
                        except Exception:
                            self._engine_alive = False

                elif msg_type == 'set_voice':
                    try:
                        engine.setProperty('voice', msg['voice_id'])
                    except Exception as e:
                        print(f"SpeechEngine: set_voice error: {e}")

                elif msg_type == 'set_rate':
                    try:
                        engine.setProperty('rate', int(msg['rate']))
                    except Exception as e:
                        print(f"SpeechEngine: set_rate error: {e}")

                elif msg_type == 'init_voices':
                    try:
                        self.voices = list(engine.getProperty('voices') or [])
                    except Exception as e:
                        print(f"SpeechEngine: init_voices error: {e}")

                self._speech_queue.task_done()

            except Exception as e:
                print(f"SpeechEngine: worker loop error: {e}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_voices(self) -> List[str]:
        """Return list of available voice display names."""
        try:
            return [getattr(v, 'name', str(v)) for v in self.voices]
        except Exception:
            return []

    def set_voice(self, index: int) -> bool:
        """Set voice by index. Returns True on success."""
        try:
            if _IS_ANDROID:
                return False  # Android voices managed by OS
            if 0 <= index < len(self.voices):
                self._speech_queue.put({
                    'type': 'set_voice',
                    'voice_id': self.voices[index].id
                })
                return True
        except Exception:
            pass
        return False

    def speak(self, text: str) -> None:
        """Speak text. Uses native TTS on Android, pyttsx3 on desktop."""
        try:
            if not text or not text.strip():
                return
            if _IS_ANDROID:
                if _PLYER_AVAILABLE and _plyer_tts is not None:
                    try:
                        _plyer_tts.speak(text)
                    except Exception as e:
                        print(f"SpeechEngine: Android TTS error: {e}")
            else:
                self._speech_queue.put({'type': 'speak', 'text': text})
        except Exception as e:
            print(f"SpeechEngine: speak() outer error: {e}")

    @property
    def engine(self):
        """Proxy that intercepts setProperty calls (e.g. rate changes from UI slider)."""
        class _EngineProxy:
            def __init__(self, parent: 'SpeechEngine'):
                self._parent = parent

            def setProperty(self, prop: str, value: Any) -> None:
                try:
                    if prop == 'rate' and not _IS_ANDROID:
                        self._parent._speech_queue.put({'type': 'set_rate', 'rate': value})
                except Exception:
                    pass

        return _EngineProxy(self)
