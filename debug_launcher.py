import sys
import traceback
import os

# Enable Kivy logs to stderr as well
os.environ['KIVY_NO_CONSOLE_LOG'] = '0'

try:
    from main import HandSignApp  # pyre-ignore
    app = HandSignApp()
    app.run()
except Exception as e:
    with open('absolute_crash.log', 'w') as f:
        traceback.print_exc(file=f)
    print("CRASH DETECTED! Check absolute_crash.log", file=sys.stderr)
    traceback.print_exc()
    sys.exit(1)
