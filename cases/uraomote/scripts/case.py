"""Where this case keeps its files. Importing it also puts the pipeline's scripts/ on sys.path, so the set
scripts here import the shared kits (cyc, mvlib, assets, props, texlib) as before."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CASE = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(CASE))
RENDERS = os.path.join(CASE, "renders")
AUDIO = os.path.join(CASE, "audio")      # the song, the vocal and their timing; not in git
if os.path.join(ROOT, "scripts") not in sys.path:
    sys.path.insert(1, os.path.join(ROOT, "scripts"))
