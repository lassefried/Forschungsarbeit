import os
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import numpy as np
import pandas as pd


class RohdatenSicherung:
    def __init__(self, verzeichnis="Ergebnisse"):
        verzeichnis = Path(verzeichnis)
        verzeichnis.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
        self.datei = verzeichnis / f"apmbRaw_{timestamp}_{uuid4().hex[:8]}.csv"
        # Exklusiv anlegen: Eine bestehende Aufnahme niemals überschreiben.
        with self.datei.open("x", encoding="utf-8"):
            pass

    def schreiben(self, block):
        block = np.asarray(block)
        if block.ndim != 2 or block.shape[1] != 9:
            raise ValueError(f"Ungültiger Rohdatenblock: {block.shape}; erwartet (N, 9).")
        # Gleiches Dateiformat wie bisher, mit höherer numerischer Präzision.
        text = pd.DataFrame(block).to_csv(
            sep="\t", decimal=",", header=False, index=False, float_format="%.17g"
        )
        with self.datei.open("a", encoding="utf-8", newline="") as datei:
            datei.write(text)
            datei.flush()
            os.fsync(datei.fileno())
