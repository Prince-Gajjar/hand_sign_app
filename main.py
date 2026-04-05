import os
import sys
import warnings
import logging
import math
import cv2  # pyre-ignore # type: ignore

# ──────────────────────────────────────────────────────────────────────
# SILENCE ALL NOISY LOGS
# ──────────────────────────────────────────────────────────────────────
warnings.filterwarnings("ignore", message="SymbolDatabase.GetPrototype")
warnings.filterwarnings("ignore", category=UserWarning, module="google.protobuf")
logging.getLogger("comtypes").setLevel(logging.WARNING)
logging.getLogger("absl").setLevel(logging.WARNING)

os.environ['KIVY_NO_CONSOLE_LOG'] = '0'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['GLOG_minloglevel'] = '2'

from kivymd.app import MDApp  # pyre-ignore # type: ignore
from kivy.lang import Builder  # pyre-ignore # type: ignore
from kivy.clock import Clock  # pyre-ignore # type: ignore
from kivy.logger import Logger  # pyre-ignore # type: ignore
from kivy.core.window import Window  # pyre-ignore # type: ignore
from kivymd.uix.screen import MDScreen  # pyre-ignore # type: ignore
from kivy.graphics.texture import Texture  # pyre-ignore # type: ignore
from kivymd.uix.dialog import MDDialog  # pyre-ignore # type: ignore
from kivymd.uix.button import MDFlatButton  # pyre-ignore # type: ignore
from kivy.uix.boxlayout import BoxLayout
from kivymd.uix.textfield import MDTextField
from kivy.uix.screenmanager import ScreenManager, FadeTransition  # type: ignore
from kivymd.uix.list import OneLineListItem  # pyre-ignore # type: ignore
from kivy.uix.scrollview import ScrollView  # pyre-ignore # type: ignore
from kivymd.uix.list import MDList  # pyre-ignore # type: ignore
from plyer import tts  # pyre-ignore # type: ignore

# Vibrator check
_HAS_VIBRATOR = False
_vibrator = None
if not sys.platform.startswith('win'):
    try:
        from plyer import vibrator as _vibrator
        if _vibrator and _vibrator.exists():
            _HAS_VIBRATOR = True
    except Exception:
        pass

from kivy.core.clipboard import Clipboard
from kivymd.uix.chip import MDChip
from kivymd.toast import toast

from gesture_database import get_translation
from supabase_manager import SupabaseManager
from typing import cast, Any, List, Optional
import queue
import threading
import time

# Portrait setup for desktop
Window.size = (450, 800)

from kivy.properties import StringProperty, ListProperty, NumericProperty

class LoginScreen(MDScreen): pass
class SignUpScreen(MDScreen): pass
class CustomGesturesScreen(MDScreen): pass
class HelpScreen(MDScreen): pass
class MainScreen(MDScreen):
    def on_enter(self):
        app = MDApp.get_running_app()
        if hasattr(app, 'start_updates'): app.start_updates()

    def on_leave(self):
        app = MDApp.get_running_app()
        if hasattr(app, 'stop_updates'): app.stop_updates()

class HandSignApp(MDApp):
    dialog = None
    current_lang = StringProperty('English')
    history = ListProperty([])
    sentence = ListProperty([])
    session_count = NumericProperty(0)
    available_voices = ListProperty([])
    current_voice_index = NumericProperty(0)
    last_detect_time = NumericProperty(0)
    auto_speak_enabled = StringProperty('ON')
    confidence_text = StringProperty("")

    bg_anim_v1 = NumericProperty(0)
    bg_anim_v2 = NumericProperty(0)
    logo_float = NumericProperty(0)

    _processing = False
    _frame_count = 0
    _preview_texture: Optional[Any] = None
    _shutting_down = False

    def _vibrate(self, duration=0.1):
        if _HAS_VIBRATOR and _vibrator:
            try: _vibrator.vibrate(time=duration)
            except Exception: pass

    def _extract_auth_user(self, res):
        if res is None:
            return None
        if isinstance(res, dict):
            user = res.get('user')
            if user:
                return user
            session = res.get('session')
            if isinstance(session, dict):
                return session.get('user')
            return None
        user = getattr(res, 'user', None)
        if user:
            return user
        session = getattr(res, 'session', None)
        if session is not None:
            return getattr(session, 'user', None)
        data = getattr(res, 'data', None)
        if isinstance(data, dict):
            user = data.get('user')
            if user:
                return user
            session = data.get('session')
            if isinstance(session, dict):
                return session.get('user')
        return None

    def _extract_auth_session(self, res):
        if res is None:
            return None
        if isinstance(res, dict):
            session = res.get('session')
            if session:
                return session
            data = res.get('data')
            if isinstance(data, dict):
                return data.get('session')
            return None
        session = getattr(res, 'session', None)
        if session:
            return session
        data = getattr(res, 'data', None)
        if isinstance(data, dict):
            return data.get('session')
        return None

    def _handle_authenticated_user(self, res, success_message: str, allow_main: bool = True):
        user_obj = self._extract_auth_user(res)
        if user_obj is None and self.supabase:
            try:
                user_res, _ = self.supabase.get_user()
                user_obj = self._extract_auth_user(user_res)
            except Exception as e:
                Logger.warning(f"Auth: User lookup failed: {e}")

        if user_obj is None:
            return False

        if success_message:
            toast(success_message)
        if allow_main:
            self.load_cloud_gestures()
            self.change_screen('main')
        return True

    def _clear_cloud_gestures(self):
        if self.detector and hasattr(self.detector, 'custom_gestures'):
            self.detector.custom_gestures.clear()
            try:
                self.refresh_gestures_list()
            except Exception:
                pass

    def build(self):
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Teal"
        self.theme_cls.accent_palette = "Amber"

        try:
            self.supabase = SupabaseManager()
        except Exception as e:
            Logger.error(f"App: Supabase init failed: {e}")
            self.supabase = None

        self.camera = None
        self.detector = None
        self.speech_engine = None
        self.detect_queue = queue.Queue(maxsize=1)

        # Start workers
        threading.Thread(target=self._detector_worker, daemon=True, name="DetectorWorker").start()
        threading.Thread(target=self.initialize_modules, daemon=True, name="ModuleInit").start()

        Clock.schedule_interval(self._animate_background, 1.0 / 60.0)

        Builder.load_file('ui/auth_screens.kv')
        Builder.load_file('ui/main_screen.kv')

        self.sm = ScreenManager(transition=FadeTransition(duration=0.3))
        self.sm.add_widget(LoginScreen(name='login'))
        self.sm.add_widget(SignUpScreen(name='signup'))
        self.sm.add_widget(MainScreen(name='main'))
        self.sm.add_widget(CustomGesturesScreen(name='gestures'))
        self.sm.add_widget(HelpScreen(name='help'))

        self.sm.current = 'login'
        threading.Thread(target=self._check_session, daemon=True).start()

        return self.sm

    def _check_session(self):
        if not self.supabase:
            return
        session_res, session_err = self.supabase.load_session()
        if session_err and session_err not in ("No local session found", "Invalid local session format"):
            Logger.warning(f"Auth: Session restore skipped: {session_err}")

        user = self._extract_auth_user(session_res)
        if user is None:
            try:
                user_res, error = self.supabase.get_user()
                if error:
                    Logger.warning(f"Auth: User check failed: {error}")
                user = self._extract_auth_user(user_res)
            except Exception as e:
                Logger.warning(f"Auth: User check exception: {e}")

        if user:
            Clock.schedule_once(lambda dt: self._clear_cloud_gestures(), 0)
            Clock.schedule_once(lambda dt: self.load_cloud_gestures(), 0)
            Clock.schedule_once(lambda dt: self.change_screen('main'), 0)

    def initialize_modules(self):
        try:
            from camera_module import CameraFeed
            from gesture_detector import GestureDetector
            from speech_engine import SpeechEngine

            Logger.info("App: Loading modules...")
            self.camera = CameraFeed()
            self.detector = GestureDetector()
            self.speech_engine = SpeechEngine()

            if self.speech_engine:
                voices = self.speech_engine.get_voices()
                Clock.schedule_once(lambda dt: setattr(self, 'available_voices', voices), 0)

            Logger.info("App: Modules loaded")
        except Exception as e:
            Logger.error(f"App: Module init error: {e}")

    def _animate_background(self, dt):
        t = Clock.get_time()
        self.bg_anim_v1 = math.sin(t * 0.5) * 40
        self.bg_anim_v2 = math.cos(t * 0.7) * 30
        self.logo_float = math.sin(t * 1.5) * 8

    def start_updates(self):
        Clock.unschedule(self.update)
        Clock.schedule_interval(self.update, 1.0 / 30.0)

    def stop_updates(self):
        Clock.unschedule(self.update)

    def change_screen(self, screen_name):
        try: self.sm.current = screen_name
        except Exception: pass

    # Auth logic
    def login(self, email, password):
        email = (email or "").strip()
        password = (password or "").strip()
        if not email or not password:
            toast("Email and password required")
            return
        threading.Thread(target=self._do_login, args=(email, password), daemon=True).start()

    def _do_login(self, email, password):
        if not self.supabase:
            Clock.schedule_once(lambda dt: self._on_login_result(None, "Auth service unavailable"), 0)
            return
        try:
            res, err = self.supabase.sign_in(email, password)
        except Exception as e:
            res, err = None, str(e)
        Clock.schedule_once(lambda dt: self._on_login_result(res, err), 0)

    def _on_login_result(self, res, err):
        if err:
            toast(f"Login failed: {err}")
            return

        if not self._handle_authenticated_user(res, "Login successful!"):
            toast("Login failed: invalid auth response")

    def signup(self, email, password, confirm):
        email = (email or "").strip()
        password = (password or "").strip()
        confirm = (confirm or "").strip()
        if not email or not password or not confirm:
            toast("All fields are required")
            return
        if password != confirm:
            toast("Passwords mismatch")
            return
        threading.Thread(target=self._do_signup, args=(email, password), daemon=True).start()

    def _do_signup(self, email, password):
        if not self.supabase:
            Clock.schedule_once(lambda dt: toast("Auth service unavailable"), 0)
            return
        try:
            res, err = self.supabase.sign_up(email, password)
        except Exception as e:
            res, err = None, str(e)
        Clock.schedule_once(lambda dt: self._on_signup_result(res, err), 0)

    def _on_signup_result(self, res, err):
        if err:
            toast(f"Signup failed: {err}")
            return

        user_obj = self._extract_auth_user(res)
        session_obj = self._extract_auth_session(res)
        if user_obj is not None and session_obj is not None:
            if self._handle_authenticated_user(res, "Signup successful!"):
                return

        toast("Signup successful. Check your email if confirmation is enabled.")
        self.change_screen('login')

    def logout(self):
        if self.supabase:
            self.supabase.sign_out()
        self._clear_cloud_gestures()
        self.change_screen('login')

    # Update logic
    def update(self, dt):
        if not self.camera: return
        ret, frame = self.camera.get_frame()
        if not ret or frame is None: return

        self._frame_count += 1

        # Detection cycle
        if self.detector and not self._processing and self._frame_count % 3 == 0:
            self._processing = True
            try:
                # Clear queue before putting new frame
                while not self.detect_queue.empty(): self.detect_queue.get_nowait()
                self.detect_queue.put_nowait(frame.copy())
            except Exception:
                self._processing = False

        # Visual overlay of landmarks
        if self.detector and getattr(self.detector, 'last_landmarks', None):
            for hl in self.detector.last_landmarks:
                self.detector.mp_draw.draw_landmarks(
                    frame, hl, self.detector.mp_hands.HAND_CONNECTIONS,
                    self.detector.mp_draw.DrawingSpec(color=(0, 200, 180), thickness=2),
                    self.detector.mp_draw.DrawingSpec(color=(255, 255, 255), thickness=1)
                )

        self._display_frame(frame)

    def _display_frame(self, frame):
        try:
            main_screen = self.sm.get_screen('main')
            preview = main_screen.ids.camera_preview
            h, w = frame.shape[:2]

            if not self._preview_texture or self._preview_texture.size != (w, h):
                self._preview_texture = Texture.create(size=(w, h), colorfmt='bgr')
                self._preview_texture.flip_vertical()
                preview.texture = self._preview_texture

            self._preview_texture.blit_buffer(frame.tobytes(), colorfmt='bgr', bufferfmt='ubyte')
            preview.canvas.ask_update()
        except Exception: pass

    def _detector_worker(self):
        while not self._shutting_down:
            try:
                frame = self.detect_queue.get(timeout=1.0)
                if frame is None: break

                det = self.detector
                if det:
                    _, gesture, conf = det.detect(frame)
                    Clock.schedule_once(lambda dt, g=gesture, c=conf: self._on_detection_complete(g, c), 0)
            except queue.Empty: continue
            except Exception: pass
            finally: self._processing = False

    def _on_detection_complete(self, gesture, confidence):
        try:
            if gesture:
                self.confidence_text = f"{int(confidence*100)}% Match"
                self.process_gesture(gesture)
                self.last_detect_time = Clock.get_time()
            else:
                self.confidence_text = ""
                # Auto-speak logic
                if (self.auto_speak_enabled == 'ON' and self.sentence
                    and Clock.get_time() - self.last_detect_time > 2.5):
                    self.speak_sentence()
                    self.last_detect_time = Clock.get_time() + 10 # Block repeat
                    self.sentence = []
        except Exception: pass

    def process_gesture(self, gesture):
        try:
            if gesture == "EMERGENCY":
                self.trigger_emergency()
                return

            translated = get_translation(gesture, self.current_lang)
            main_screen = self.sm.get_screen('main')
            main_screen.ids.current_gesture.text = translated

            if not self.history or self.history[-1] != translated:
                self.history.append(translated)
                self.sentence.append(translated)
                if len(self.history) > 50: self.history = self.history[-50:]

                formatted = " ".join(self.sentence)
                if formatted: formatted = formatted.capitalize()
                main_screen.ids.conversation_output.text = formatted

                self.session_count += 1
                self.update_suggestions(translated)
                self._vibrate(0.1)
        except Exception: pass

    def update_suggestions(self, last_word):
        preds = {
            "HELLO": ["HOW", "ARE", "YOU", "FRIEND"],
            "HELP": ["ME", "PLEASE", "URGENT"],
            "I": ["NEED", "WANT", "AM", "LOVE"],
            "THANK": ["YOU", "VERY", "MUCH"]
        }
        try:
            box = self.sm.get_screen('main').ids.suggestion_box
            box.clear_widgets()
            suggestions = preds.get(last_word.upper(), ["PLEASE", "THANK", "HELP", "WANT"])
            for word in suggestions:
                box.add_widget(MDChip(text=word, on_release=lambda x: self.add_suggested_word(x.text)))
        except Exception: pass

    def add_suggested_word(self, word):
        self.sentence.append(word)
        try:
            self.sm.get_screen('main').ids.conversation_output.text = " ".join(self.sentence).capitalize()
        except Exception: pass

    def speak_sentence(self):
        if not self.speech_engine: return
        try:
            text = self.sm.get_screen('main').ids.conversation_output.text
            if text.strip():
                rate = self.sm.get_screen('main').ids.voice_slider.value
                self.speech_engine.engine.setProperty('rate', int(rate))
                self.speech_engine.speak(text)
        except Exception: pass

    def clear_sentence(self):
        self.sentence = []
        try:
            screen = self.sm.get_screen('main')
            screen.ids.conversation_output.text = ""
            screen.ids.current_gesture.text = "Ready"
        except Exception: pass

    def save_custom_gesture(self):
        try:
            phrase = self.gesture_input.text.strip().upper()
            if not phrase or not self.detector or not self.detector.last_features:
                toast("Invalid gesture or phrase")
                return

            features = list(self.detector.last_features)
            self.detector.custom_gestures[phrase] = features
            if hasattr(self, 'custom_gesture_dialog'): self.custom_gesture_dialog.dismiss()

            threading.Thread(target=self._save_gesture_bg, args=(phrase, features), daemon=True).start()
        except Exception: toast("Save error")

    def _save_gesture_bg(self, phrase, features):
        if self.supabase:
            user_res, _ = self.supabase.get_user()
            user = getattr(user_res, 'user', user_res)
            if user and hasattr(user, 'id'):
                self.supabase.save_custom_gesture(user.id, phrase, features)
                Clock.schedule_once(lambda dt: toast(f"Saved: {phrase}"), 0)
                return
        Clock.schedule_once(lambda dt: toast("Please sign in to save gestures"), 0)

    def load_cloud_gestures(self):
        threading.Thread(target=self._load_gestures_bg, daemon=True).start()

    def _load_gestures_bg(self):
        if self.supabase and self.detector:
            user_res, _ = self.supabase.get_user()
            user = getattr(user_res, 'user', user_res)
            if user and hasattr(user, 'id'):
                data, _ = self.supabase.get_custom_gestures(user.id)
                if data:
                    for row in data:
                        self.detector.custom_gestures[row['phrase']] = row['features']
                    Clock.schedule_once(lambda dt: self.refresh_gestures_list(), 0)
                else:
                    Clock.schedule_once(lambda dt: self._clear_cloud_gestures(), 0)
            else:
                Clock.schedule_once(lambda dt: self._clear_cloud_gestures(), 0)

    def refresh_gestures_list(self):
        try:
            list_view = self.sm.get_screen('gestures').ids.gestures_list
            list_view.clear_widgets()
            from kivymd.uix.list import TwoLineAvatarIconListItem, IconRightWidget
            for p in self.detector.custom_gestures.keys():
                item = TwoLineAvatarIconListItem(text=p, secondary_text="Custom Phrase")
                item.add_widget(IconRightWidget(icon="delete", on_release=lambda x, p=p: self.delete_gesture(p)))
                list_view.add_widget(item)
        except Exception: pass

    def delete_gesture(self, phrase):
        if self.detector and phrase in self.detector.custom_gestures:
            del self.detector.custom_gestures[phrase]
            self.refresh_gestures_list()

    def recalibrate(self):
        if self.detector:
            self.detector.detection_buffer.clear()
            self.detector.cooldown = 0
            toast("Detector Reset")

    def trigger_emergency(self):
        if self.speech_engine:
            msg = get_translation("EMERGENCY_MSG", self.current_lang)
            self.speech_engine.speak(msg)
            self._vibrate(2)

    def set_language(self, l):
        self.current_lang = l
        toast(f"Language: {l}")
        if hasattr(self, '_lang_dialog'): self._lang_dialog.dismiss()

    def toggle_auto_speak(self):
        self.auto_speak_enabled = "ON" if self.auto_speak_enabled == "OFF" else "OFF"
        toast(f"Auto-Speak: {self.auto_speak_enabled}")

    def flip_camera(self):
        if self.camera: self.camera.switch_camera()

    def on_stop(self):
        self._shutting_down = True
        try: self.detect_queue.put_nowait(None)
        except Exception: pass
        if self.camera: self.camera.release()

    def copy_to_clipboard(self):
        try:
            text = self.sm.get_screen('main').ids.conversation_output.text
            if text.strip():
                Clipboard.copy(text)
                toast("Copied to clipboard")
            else:
                toast("Nothing to copy yet")
        except Exception as e:
            Logger.warning(f"Clipboard copy failed: {e}")
            toast("Copy failed")

    def show_history_dialog(self):
        try:
            items = self.history[-15:] if self.history else []
            body = "\n".join(f"• {item}" for item in items) if items else "No detection history yet."
            if self.dialog:
                self.dialog.dismiss()
            self.dialog = MDDialog(
                title="Detection History",
                text=body,
                buttons=[MDFlatButton(text="CLOSE", on_release=lambda x: self.dialog.dismiss())],
            )
            self.dialog.open()
        except Exception as e:
            Logger.warning(f"History dialog failed: {e}")
            toast("Could not open history")

    def export_session(self):
        try:
            export_base = getattr(self, 'user_data_dir', None) or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'exports')
            os.makedirs(export_base, exist_ok=True)
            filename = f"session_{int(time.time())}.txt"
            path = os.path.join(export_base, filename)
            with open(path, "w", encoding="utf-8") as f:
                f.write("HandSign AI Session Export\n")
                f.write(f"Language: {self.current_lang}\n")
                f.write(f"Detections: {self.session_count}\n")
                f.write("\nConversation:\n")
                f.write(self.sm.get_screen('main').ids.conversation_output.text or "")
                f.write("\n\nHistory:\n")
                for item in self.history:
                    f.write(f"- {item}\n")
            toast(f"Exported to {filename}")
        except Exception as e:
            Logger.warning(f"Export failed: {e}")
            toast("Export failed")

    def show_custom_gestures_dialog(self):
        try:
            if self.dialog:
                self.dialog.dismiss()
            self.gesture_input = MDTextField(hint_text="Custom phrase", multiline=False)
            content = BoxLayout(orientation="vertical", spacing=12, padding=12)
            content.add_widget(self.gesture_input)
            self.custom_gesture_dialog = MDDialog(
                title="Save Custom Gesture",
                type="custom",
                content_cls=content,
                buttons=[
                    MDFlatButton(text="CANCEL", on_release=lambda x: self.custom_gesture_dialog.dismiss()),
                    MDFlatButton(text="SAVE", on_release=lambda x: self.save_custom_gesture()),
                ],
            )
            self.custom_gesture_dialog.open()
        except Exception as e:
            Logger.warning(f"Custom gestures dialog failed: {e}")
            toast("Could not open custom gesture dialog")
