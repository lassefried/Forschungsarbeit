#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Aug 13 17:56:03 2026

@author: lasse
"""

#Grafikmodul

import sys
import numpy as np

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QFileDialog
)
from PySide6.QtCore import QObject, QThread, Signal, QUrl, Qt, Slot
from durchführung import durchführungAnalyse
from PySide6.QtWebEngineWidgets import QWebEngineView

from pathlib import Path
# ALT: from kalibrierFenster import (KalibrierFenster)
from kalibrierFenster import KalibrierFenster, marker_zuruecksetzen
from gantner import GantnerMessung
from remote import RemoteMessung
# NEU: Blockweise Sicherung unabhängig vom späteren Analyseergebnis.
# ALT: from rohdaten import RohdatenSicherung
from durchführung import RohdatenSicherung


class MeasurementWorker(QObject):

    finished = Signal(object, object, object)
    error = Signal(str)
    status = Signal(str)

    def __init__(self, messgeraet_klasse):
        super().__init__()

        self.stop_angefordert = False
        self.messgeraet = None
        self.messgeraet_klasse = messgeraet_klasse


    @Slot()

    def run(self):

        bloecke = []
        #Bei Simulation bleiben die vorhandenen Quelldaten unverändert.
        rohdaten_sicherung = None

        try:
            self.stop_angefordert = False

            self.messgeraet = self.messgeraet_klasse()
            
            remote_modus = isinstance(self.messgeraet, RemoteMessung)

            self.status.emit("Verbinde mit Q.station ...")

            self.messgeraet.verbinden()

            abtastrate = (self.messgeraet.abtastrate)

            #Vor Messbeginn prüfen, ob eine Rohdatei angelegt werden kann.
            if not remote_modus:
                rohdaten_sicherung = RohdatenSicherung()
                self.status.emit(f"Rohdaten werden gesichert: {rohdaten_sicherung.datei}")

            self.messgeraet.messung_starten()

            self.status.emit("Messung läuft ...")

            
            # Kontinuierliche Messung
            samples = 0

            while not self.stop_angefordert:
            
                try:
                    block = self.messgeraet.datenblock_lesen()
            
                except StopIteration:
                    self.status.emit("Ende der Messdaten erreicht.")
                    break
            
                print("Empfangener Block:", block.shape)

                #Erst auf Datenträger sichern, dann für die Analyse sammeln.
                if rohdaten_sicherung is not None:
                    rohdaten_sicherung.schreiben(block)
            
                bloecke.append(block)
            
                samples += len(block)
            
                messdauer = samples / abtastrate
            
                self.status.emit(
                    f"Messung läuft: {messdauer:.1f} s"
                )
                        
            
            print("DEBUG 1: Messschleife verlassen")

            # Messung beendet
            self.status.emit("Messung beendet – Auswertung läuft ...")
            
            print("DEBUG 2: Messgerät trennen")

            self.messgeraet.trennen()
            
            print("DEBUG 3: Anzahl Blöcke:",len(bloecke))

            if not bloecke:

                raise RuntimeError("Keine Messdaten aufgenommen.")
                
            print("DEBUG 4: concatenate startet")

            # Alle Gantner-Blöcke zusammenfügen
            datenblock = np.concatenate( bloecke, axis=0)
            
            print(
                "DEBUG 5: concatenate fertig:",
                datenblock.shape,
                datenblock.nbytes / 1024 / 1024,
                "MB"
            )

            print("Gesamter Datenblock:", datenblock.shape)
            
            # Alte Blöcke werden nicht mehr benötigt
            bloecke.clear()

            print("DEBUG 6: durchführungAnalyse startet")

            (
                daten_kalibriert,
                ergebnisse,
                html_datei
            ) = durchführungAnalyse(
                datenblock,
                abtastrate,

                remote_modus=remote_modus,
                rohdatei=(rohdaten_sicherung.datei
                          if rohdaten_sicherung is not None else None)
            )
                
            print("DEBUG 7: durchführungAnalyse fertig")

            self.finished.emit( daten_kalibriert, ergebnisse, html_datei)
            
            print("DEBUG 8: finished gesendet")

        except Exception as e:

            #Auch bei Geräte-/Analysefehlern ist die Rohdatei auffindbar.
            hinweis = ""
            if rohdaten_sicherung is not None:
                hinweis = (f"\nRohdatei: {rohdaten_sicherung.datei.resolve()}"
                           "\nDie Aufnahme kann unvollständig sein.")
            self.error.emit(f"{type(e).__name__}: {e}{hinweis}")

        finally:

            if self.messgeraet is not None:

                try:
                    self.messgeraet.trennen()
                except Exception:
                    pass


    def stoppen(self):

        self.stop_angefordert = True


class Grafikmodul(QMainWindow):

    def __init__(self):
        super().__init__()

        #Auch beim direktem Öffnen des Hauptfensters beide Marker aktivieren.
        marker_zuruecksetzen()
        
        self.kalibrierfenster = None
        self.thread = None
        self.worker = None

        # Fenster
        self.setWindowTitle("Messprogramm")
        self.resize(1400, 800)

        # Zentrales Widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Layout
        layout = QVBoxLayout()        
        central_widget.setLayout(layout)

        # Überschrift
        self.label = QLabel("Bereit")
        self.label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label, 1)

        
        button_layout = (QHBoxLayout())
        
        
        self.start_button = (QPushButton("Messung starten"))
        self.stop_button = QPushButton("Messung stoppen")
        self.stop_button.setEnabled(False)
        


        self.kalibrier_button = (QPushButton("Sensoren / Kalibrierung"))
        
        self.html_button = QPushButton("Vorigen Versuch laden")
        
        button_layout.addStretch()

        button_layout.addWidget(self.start_button)
        
        button_layout.addWidget(self.stop_button)
        
        button_layout.addWidget(self.kalibrier_button)
        
        button_layout.addWidget(self.html_button)

        button_layout.addStretch()


        layout.addLayout(button_layout)
        

        
        self.web_view = QWebEngineView()
        layout.addWidget(self.web_view, 6)
        
        self.start_button.clicked.connect(self.start_Messung)
        
        self.stop_button.clicked.connect(self.stop_messung)


        self.kalibrier_button.clicked.connect(self.kalibrierfenster_auf)
        
        self.html_button.clicked.connect(self.html_laden)



    def start_Messung(self):
        
        # Doppelte Messung verhindern
        if self.thread is not None:
            return

        
        
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        
        self.label.setText("Analyse läuft...")
        
        self.thread = QThread()
        
        self.worker = MeasurementWorker(RemoteMessung)   #GantnerMessung / RemoteMessung
        
        self.worker.moveToThread(self.thread)
        
        self.thread.started.connect(self.worker.run)
        
        self.worker.status.connect(self.label.setText)
        
        self.worker.finished.connect(self.measurement_finished)
        
        self.worker.finished.connect(self.thread.quit)

        self.worker.error.connect(self.measurement_error)
        
        self.worker.error.connect(self.thread.quit)
        
        self.thread.finished.connect(self.thread_aufraeumen)

        self.thread.start()


    def stop_messung(self):

        if self.worker is None:
            return

        self.stop_button.setEnabled(False)

        self.label.setText("Messung wird beendet ...")

        self.worker.stoppen()   
        
        
    def measurement_finished(
        self,
        daten_kalibriert, ergebnisse, htmlDatei):

        self.label.setText("Analyse abgeschlossen")
   
        self.stop_button.setEnabled(False)

       
        html_path = Path(htmlDatei).resolve()

        self.web_view.load(QUrl.fromLocalFile(str(html_path)))

        

    def measurement_error(self, message):

        self.label.setText("Fehler bei der Messung")

        print("Fehler:", message)

        self.start_button.setEnabled(True)
        
        self.stop_button.setEnabled(False)

    
    def thread_aufraeumen(self):

        if self.worker is not None:
            self.worker.deleteLater()

        if self.thread is not None:
            self.thread.deleteLater()

        self.worker = None
        self.thread = None
        
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
    
    
            
    def kalibrierfenster_auf(self):
       
        if (self.kalibrierfenster
           is None):
           
           self.kalibrierfenster = (KalibrierFenster())
           
           self.kalibrierfenster.destroyed.connect(self.kalibrierfenster_zu)
       
        self.kalibrierfenster.show()
        self.kalibrierfenster.raise_()
        self.kalibrierfenster.activateWindow()
        
    def kalibrierfenster_zu(self):
        
        self.kalibrierfenster = None
        


    def html_laden(self):
        datei, _ = QFileDialog.getOpenFileName(
            self,
            "HTML-Datei auswählen",
            "",
            "HTML-Dateien (*.html *.htm)"
            )

        if datei:
            self.web_view.load(QUrl.fromLocalFile(datei))







       
