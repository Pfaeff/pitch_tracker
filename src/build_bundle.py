import os
import subprocess
import shutil
import main

DIST_DIR = "dist"

README_FILE_TEMPLATE = "README.template.txt"
README_FILE = "README.txt"

DIRS_TO_COPY = ["resources"]
FILES_TO_COPY = ["config.cfg", README_FILE, "LICENSE.txt"]

# Remove dist directory if it exists
if os.path.exists(DIST_DIR):
    shutil.rmtree(DIST_DIR)

# Run pyinstaller
PYINSTALLER_COMMAND = ["pyinstaller", "--onefile", "--noconsole", "--icon", "icon.ico", "--name", "PitchTracker", "main.py"]
print("Runing pyinstaller using command:", " ".join(PYINSTALLER_COMMAND))
subprocess.call(PYINSTALLER_COMMAND)

# Write Version number to readme file
with open(README_FILE_TEMPLATE, "rt") as f:
    readme_text = f.read()

readme_text = readme_text.format(version=main.VERSION)    

with open(README_FILE, "wt") as f:
    f.write(readme_text)

for d in DIRS_TO_COPY:
    name = os.path.basename(d)
    print("Copying directory '{d}'...".format(d=d))

    target_dir = os.path.join(DIST_DIR, name)
    shutil.copytree(d, target_dir)

for f in FILES_TO_COPY:
    print("Copying file '{f}'...".format(f=f))
    shutil.copy2(f, DIST_DIR)

zip_filename = 'PitchTracker_{version}'.format(version=main.VERSION)
shutil.make_archive(zip_filename, 'zip', DIST_DIR)

os.remove(README_FILE)

print("Done.")