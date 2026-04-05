import os
import sys
import traceback
import threading
import time

# Force Kivy logs
os.environ['KIVY_NO_CONSOLE_LOG'] = '0'

def monitor_threads():
    while True:
        print(f"Active threads: {threading.active_count()}", file=sys.stderr)
        for t in threading.enumerate():
            print(f"  Thread: {t.name}, Daemon: {t.daemon}, Alive: {t.is_alive()}", file=sys.stderr)
        time.sleep(5)

# threading.Thread(target=monitor_threads, daemon=True).start()

try:
    from main import HandSignApp  # pyre-ignore
    print("App class imported")
    app = HandSignApp()
    print("App instance created")
    app.run()
    print("App finished normally")
except Exception as e:
    print("\n" + "="*50)
    print("CRASH DETECTED IN MAIN THREAD")
    traceback.print_exc()
    print("="*50)
    sys.exit(1)
