#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Aug  9 18:10:04 2026

@author: lasse
"""

import os, sys, math
import plotly.graph_objects as go    #import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from datetime import datetime
from pathlib import Path


from Analyse import SignalAnalyse
from PySide6.QtWidgets import QApplication
from Grafikmodul import Grafikmodul
# ALT: from kalibrierFenster import marker_zuruecksetzen

#source PyEv/bin/activate
#cd /home/lasse/Dokumente/Uni/Forschungsarbeit/02_ersteAuswertungAPMB
#technologiefelder der wasserkraft do 14uhr
#ilias campus ...

def main():

    app = QApplication(sys.argv)
    # ALT: marker_zuruecksetzen() – erfolgt jetzt im Konstruktor von Grafikmodul.

    window = Grafikmodul()
    window.show()

    sys.exit(app.exec())
    
if __name__== "__main__":
    main()






