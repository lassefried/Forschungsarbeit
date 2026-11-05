#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Sep  30 10:32:01 2026

@author: lasse
"""


from pathlib import Path
import time

import numpy as np
import pandas as pd


class RemoteFehler(Exception):
    
    pass


class RemoteMessung:

    def __init__(
        self,
        datei="apmbKali",
        abtastrate=10_000,
        blockdauer=0.1
    ):
        """
        Parameter
        ---------
        datei:
            Pfad zur vorhandenen apmbKali-Datei.

        abtastrate:
            Abtastrate der ursprünglichen Messung in Hz.

        blockdauer:
            Dauer eines simulierten Datenblocks in Sekunden.
            Standard: 0.1 s = 100 ms.
        """

        self.datei = Path(datei)

        self.abtastrate = float(abtastrate)
        self.blockdauer = float(blockdauer)

        # Anzahl Samples pro Block
        self.blockgroesse = int(
            
                self.abtastrate
                * self.blockdauer
            
        )

        if self.blockgroesse <= 0:
            raise ValueError(
                "Die Blockgröße muss größer als 0 sein."
            )

        # -----------------------------------------------------
        # Eigenschaften entsprechend der Gantner-Schnittstelle
        # -----------------------------------------------------

        self.kanalzahl = 9

        self.kanalnamen = [
            "Timestamp",
            "Variable 1",
            "Variable 2",
            "Variable 3",
            "Variable 4",
            "Variable 5",
            "Variable 6",
            "Variable 7",
            "Variable 8"
        ]

        self.verbunden = False
        self.messung_laeuft = False

        # -----------------------------------------------------
        # Interner Zustand
        # -----------------------------------------------------

        self._daten = None

        self._position = 0

        self._naechster_zeitpunkt = None


    # =========================================================
    # Verbindung
    # =========================================================

    def verbinden(self):
        """
        Simuliert das Verbinden mit der Q.station.

        Tatsächlich wird nur geprüft, ob die angegebene
        apmbKali-Datei existiert.
        """

        if self.verbunden:
            return

        if not self.datei.exists():
            raise RemoteFehler(
                "Remote-Messdatei nicht gefunden:\n"
                f"{self.datei.resolve()}"
            )

        self.verbunden = True

        print(
            "Remote-Schnittstelle verbunden:"
        )

        print(
            self.datei.resolve()
        )


    # =========================================================
    # Messung starten
    # =========================================================

    def messung_starten(self):
        """
        Liest die apmbKali-Datei vollständig ein und bereitet
        die simulierte Messung vor.
        """

        if not self.verbunden:
            self.verbinden()

        if self.messung_laeuft:
            return

        try:

            rohdata = pd.read_csv(
                self.datei,
                header=None,
                sep=r"\s+",
                decimal=","
                )

        except Exception as e:

            raise RemoteFehler(
                f"Fehler beim Lesen der Datei: {e}"
                ) from e

        # -----------------------------------------------------
        # Alte apmbKali-Struktur
        # -----------------------------------------------------
        #
        # Bisher:
        #
        # data = data.iloc[:, 1:-1]
        #
        # Danach:
        #
        # p1 p2 p3 p4 p5 p6 Q
        #
        # -> 7 Messkanäle
        # -----------------------------------------------------
        
        # Vollständigen Q.station-Datenblock erwarten
        if rohdata.shape[1] != 9:
        
            raise RemoteFehler(
                "Unerwartete Rohdatenstruktur.\n"
                f"Gefundene Spalten: {rohdata.shape[1]}\n"
                "Erwartet werden 9 Spalten "
                "(Timestamp + 8 Hardware-Kanäle)."
            )
        
        try:
            self._daten = rohdata.to_numpy(dtype=float)
        
        except (ValueError, TypeError) as e:
            raise RemoteFehler(
                f"Rohdaten enthalten ungültige Werte: {e}"
            ) from e
        
        anzahl_samples = len(self._daten)
        
        # Zeitachse für die Remote-Simulation rekonstruieren
        self._daten[:, 0] = (
            np.arange(anzahl_samples, dtype=float)
            / self.abtastrate
        )
        

        # messwerte = (
        #     rohdata
        #     .iloc[:, 1:-1]
        #     .to_numpy(dtype=float)
        # )

        # if messwerte.shape[1] != 7:

        #     raise RemoteFehler(
        #         "Unerwartete apmbKali-Struktur.\n"
        #         f"Gefundene Messkanäle: "
        #         f"{messwerte.shape[1]}\n"
        #         "Erwartet werden 7."
        #     )

        # anzahl_samples = len(messwerte)   
        # self._daten = np.zeros(
        #     (
        #         anzahl_samples,
        #         self.kanalzahl
        #     ),
        #     dtype=float
        # )

        # self._daten[:, 0] = (
        #     np.arange(
        #         anzahl_samples,
        #         dtype=float
        #     )
        #     / self.abtastrate
        # )
        # # -----------------------------------------------------
        # # Messwerte übernehmen
        # # -----------------------------------------------------

        # self._daten[:, 1:8] = messwerte

        # # Variable 8 bleibt unbenutzt
        # self._daten[:, 8] = 0.0

        # -----------------------------------------------------
        # Simulation zurücksetzen
        # -----------------------------------------------------

        self._position = 0

        self.messung_laeuft = True

        # Der erste Block darf sofort gelesen werden.
        self._naechster_zeitpunkt = (
            time.monotonic()
        )

        messdauer = (
            anzahl_samples
            / self.abtastrate
        )

        print()
        print("Remote-Messung gestartet")

        print(
            f"Samples:       {anzahl_samples}"
        )

        print(
            f"Abtastrate:    "
            f"{self.abtastrate:.0f} Hz"
        )

        print(
            f"Messdauer:     "
            f"{messdauer:.3f} s"
        )

        print(
            f"Blockgröße:    "
            f"{self.blockgroesse} Samples"
        )

        print(
            f"Blockdauer:    "
            f"{self.blockdauer * 1000:.0f} ms"
        )

        print()


    # =========================================================
    # Datenblock lesen
    # =========================================================

    def datenblock_lesen(self):
        """
        Gibt den nächsten 100-ms-Datenblock zurück.

        Bei 10 kHz:
            100 ms = 1000 Samples
            """

        if not self.messung_laeuft:
            raise RemoteFehler(
                "Remote-Messung läuft nicht."
                )

        if self._daten is None:
            raise RemoteFehler(
                "Keine Messdaten geladen."
                )

        # -------------------------------------------------
        # Dateiende erreicht?
        # -------------------------------------------------

        if self._position >= len(self._daten):
            self.messung_laeuft = False
            raise StopIteration

        # -------------------------------------------------
        # Auf nächsten simulierten Zeitpunkt warten
        # -------------------------------------------------

        jetzt = time.monotonic()

        if self._naechster_zeitpunkt is not None:

            wartezeit = (
                self._naechster_zeitpunkt
                - jetzt
                )

            if wartezeit > 0:
                time.sleep(wartezeit)

        # -------------------------------------------------
        # Nächsten Datenbereich bestimmen
        # -------------------------------------------------

        start = self._position

        ende = min(
            start + self.blockgroesse,
            len(self._daten)
            )

        # -------------------------------------------------
        # Block aus vorhandenen Daten ausschneiden
        # -------------------------------------------------

        block = self._daten[
            start:ende
            ].copy()

        # Neue Position
        self._position = ende

        # -------------------------------------------------
        # Nächsten Zeitpunkt festlegen
        # -------------------------------------------------

        self._naechster_zeitpunkt = (
            time.monotonic()
            + self.blockdauer
            )

        return block

    # =========================================================
    # Messung stoppen
    # =========================================================

    def messung_stoppen(self):
        """
        Stoppt die simulierte Messung.
        """

        if not self.messung_laeuft:
            return

        self.messung_laeuft = False

        print(
            "Remote-Messung gestoppt."
        )


    # =========================================================
    # Verbindung trennen
    # =========================================================

    def trennen(self):
        """
        Beendet die Remote-Schnittstelle.
        """

        self.messung_stoppen()

        self._daten = None
        self._position = 0
        self._naechster_zeitpunkt = None

        self.verbunden = False

        print(
            "Remote-Schnittstelle getrennt."
        )
