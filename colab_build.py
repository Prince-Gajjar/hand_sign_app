# HandSign AI — Google Colab APK Builder
# =========================================
# HOW TO USE:
#   1. Go to https://colab.research.google.com
#   2. Create a new notebook
#   3. Copy each CELL below into separate Colab cells
#   4. Run them one by one in order
#   5. Download the APK at the end
# =========================================


# ── CELL 1: Install system dependencies ──────────────────────────────────────
"""
%%bash
sudo apt-get update -qq
sudo apt-get install -y -qq \
    git zip unzip \
    openjdk-17-jdk \
    python3-pip \
    autoconf libtool pkg-config \
    zlib1g-dev libncurses5-dev libncursesw5-dev \
    libtinfo5 cmake libffi-dev libssl-dev \
    build-essential ccache
"""

# ── CELL 2: Install Buildozer and Cython ─────────────────────────────────────
"""
!pip install -q buildozer cython
!buildozer --version
"""

# ── CELL 3: Upload your project ZIP ──────────────────────────────────────────
"""
# Zip your entire hand_sign_app folder on YOUR PC first:
#   Right-click the folder → Send to → Compressed (zipped) folder
# Then upload it here:

from google.colab import files
uploaded = files.upload()   # upload hand_sign_app.zip

import zipfile, os
zip_name = list(uploaded.keys())[0]
with zipfile.ZipFile(zip_name, 'r') as z:
    z.extractall('/content/')

# Find the extracted folder
import glob
folders = glob.glob('/content/hand_sign_app*')
print("Extracted to:", folders)
"""

# ── CELL 4: Set working directory & verify files ─────────────────────────────
"""
import os
os.chdir('/content/hand_sign_app')
print("Files found:", os.listdir('.'))
assert 'main.py' in os.listdir('.'), "ERROR: main.py not found! Check your zip."
assert 'buildozer.spec' in os.listdir('.'), "ERROR: buildozer.spec not found!"
"""

# ── CELL 5: Verify buildozer.spec ────────────────────────────────────────────
"""
%%bash
cat buildozer.spec | head -30
"""

# ── CELL 6: Accept Android SDK licenses ──────────────────────────────────────
"""
%%bash
yes | buildozer android debug 2>&1 | head -50
# This first run will just initialise — it'll fail with license error.
# The 'yes |' pipe auto-accepts all licenses.
"""

# ── CELL 7: Build the APK (main build — takes 15-30 minutes first time) ──────
"""

%%bash
cd /content/hand_sign_app
buildozer -v android debug 2>&1 | tee /content/build_log.txt
"""

# ── CELL 8: Download the APK ──────────────────────────────────────────────────
"""
import glob
from google.colab import files

apks = glob.glob('/content/hand_sign_app/bin/*.apk')
if apks:
    print(f"✅ APK built successfully: {apks[0]}")
    files.download(apks[0])
else:
    print("❌ APK not found. Check build_log.txt below for errors.")
    # Show last 100 lines of log
    with open('/content/build_log.txt') as f:
        lines = f.readlines()
    print("\\n".join(lines[-100:]))
"""

# ── CELL 9 (Optional): Download the build log ─────────────────────────────────
"""
from google.colab import files
files.download('/content/build_log.txt')
"""
