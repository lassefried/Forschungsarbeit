#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Sep 17 14:07:19 2026

@author: lasse
"""



import socket
from ctypes import c_double
import numpy as np

import ginsapy.giutility.highspeedport as highspeedport


# KONFIGURATION


GANTNER_IP = "169.254.9.202"     #richtig

GANTNER_MODELL = "Q.Station-XB"    #richtig

ABTASTRATE = 10_000  # Hz


#TODO: print befehle entfernen wenn alles läuft



class GantnerFehler(Exception):
    """werden direkt übergeben"""
    pass


class GantnerMessung:

    def __init__(self, ip=GANTNER_IP, buffer_index=0):
        self.ip = ip
        self.buffer_index = buffer_index

        self.verbindung = None
        self.buffer_generator = None

        self.verbunden = False
        self.messung_laeuft = False

        self.abtastrate = None
        self.kanalzahl = None
        self.kanalnamen = []

        
    # INFORMATIONEN
    #TODO: Kann weg lass es aber noch drinnnen
    def informationen(self):
        if not self.verbunden:
            raise GantnerFehler("Q.station ist nicht verbunden.")

        return {
            "ip": self.ip,
            "abtastrate": self.abtastrate,
            "kanalzahl": self.kanalzahl,
            "kanalnamen": self.kanalnamen,
        }

   
    # NETZWERK TESTEN
    #TODO: #Kann weg lass es aber noch drinnnen
    def netzwerk_testen(self):
        """Prüft, ob die Q.station über das Netzwerk erreichbar ist."""

        print(f"Teste Verbindung zu {self.ip} ...")

        try:

            verbindung = socket.create_connection((self.ip, 1200),timeout=3)

            verbindung.close()

            print("Q.station ist erreichbar.")

            return True

        except OSError as fehler:

            raise GantnerFehler(
                f"Q.station unter {self.ip} "
                f"nicht erreichbar: {fehler}"
            ) from fehler



    # VERBINDUNG HERSTELLEN Stellt die Verbindung zur Q.station her

    def verbinden(self):

        if self.verbunden:
            print("Q.station ist bereits verbunden.")
            return

        try:
            self.verbindung = highspeedport.HighSpeedPortClient()
            self.verbindung.bufferindex = self.buffer_index
            self.verbindung.init_connection(self.ip)

            self.abtastrate = self.verbindung.read_sample_rate()
            self.kanalzahl = self.verbindung.read_channel_count()

            self.kanalnamen = [
                self.verbindung.read_index_name(i)
                for i in range(self.kanalzahl)
            ]

            self.verbunden = True

        except Exception as fehler:
            self.verbindung = None
            raise GantnerFehler(
                f"Verbindung zur Q.station fehlgeschlagen: {fehler}"
            ) from fehler


    # GERÄTEINFORMATIONEN Liest Controllername, Kanalanzahl und Kanalnamen aus.
    #TODO: Kann weg lass es aber noch drinnnen
    def geraeteinformationen(self):
        

        if not self.verbunden:

            raise GantnerFehler("Keine Verbindung zur Q.station.")


        # Controllername
        try:

            name = self.verbindung.read_controller_name()

            print(f"Controller: {name}")

        except Exception as fehler:

            print("Controllername konnte nicht gelesen werden:",fehler)


        # Anzahl Kanäle
        try:

            kanalzahl = (self.verbindung.read_channel_count())

            print(f"Anzahl Kanäle: {kanalzahl}")

        except Exception as fehler:

            print("Kanalanzahl konnte nicht gelesen werden:", fehler)


        # Kanalnamen
        try:

            self.kanalnamen = list(self.verbindung.read_channel_names())

            print("\nGefundene Kanäle:")

            for nummer, name in enumerate(self.kanalnamen):

                print(f"  {nummer}: {name}")

        except Exception as fehler:

            print("Kanalnamen konnten nicht gelesen werden:", fehler)

            self.kanalnamen = []

        return self.kanalnamen



    # MESSUNG STARTEN Bereitet die Messwerterfassung vor

    def messung_starten(self):

        if not self.verbunden:
            self.verbinden()

        if self.messung_laeuft:
            print("Messung läuft bereits.")
            return

        try:

            # NEU: Nach Verbindungsaufbau und Geräteabfragen ausdrücklich nur
            # aktuelle Daten anfordern. backtime=0 als Eigenschaft genügt bei
            # dieser Bibliothek nicht, weil init_connection() den Aufruf überspringt.
            ret = self.verbindung.GINSDll._CD_eGateHighSpeedPort_SetBackTime(
                self.verbindung.HCONNECTION.value, c_double(0.0)
            )
            if ret != 0:
                raise GantnerFehler(
                    f"Lesestart konnte nicht auf aktuelle Daten gesetzt werden "
                    f"(SetBackTime, Fehlercode {ret})."
                )

            # Der Generator wird erst nach erfolgreichem SetBackTime erzeugt.
            self.buffer_generator = (self.verbindung.yield_buffer())

            self.messung_laeuft = True

            print("Messung gestartet.")

        except Exception as fehler:

            raise GantnerFehler(
                f"Datenstream konnte nicht gestartet werden: "
                f"{fehler}"
                ) from fehler


    # DATENBLOCK LESEN

    def datenblock_lesen(self):
        
        if not self.messung_laeuft:
            raise GantnerFehler("Messung wurde nicht gestartet.")

        try:
            return next(self.buffer_generator)

        except StopIteration as fehler:
            self.messung_laeuft = False
            raise GantnerFehler(
                "Der Datenstrom der Q.station wurde beendet."
            ) from fehler

       


    # BUFFER TESTEN kann nach erstem test entfernt werden
    #TODO: Kann weg lass es aber noch drinnnen
    def buffer_testen(self):
                

        if not self.messung_laeuft:
            self.messung_starten()

        daten = self.datenblock_lesen()

        print("\n--- BUFFER-TEST ---")

        print("Datentyp:", type(daten))

        try:

            array = np.asarray(daten)

            print("Shape:", array.shape)

            print("Datentyp Array:", array.dtype)

            print("Erste Werte:")

            print( array[:5])

        except Exception as fehler:

            print("Buffer konnte nicht als NumPy-Array dargestellt werden:", fehler)

        return daten


 
    # MESSUNG STOPPEN Beendet die Messwerterfassung

    def messung_stoppen(self):

        self.messung_laeuft = False

        if self.buffer_generator is not None:

            try:
                self.buffer_generator.close()
            except Exception:
                pass

        self.buffer_generator = None



    # VERBINDUNG TRENNEN Beendet Messung und Verbindung zur Q.station

    def trennen(self):

        self.messung_stoppen()

        if self.verbindung is not None:

            try:
                self.verbindung.close_connection()
            except Exception:
                pass

        self.verbindung = None
        self.verbunden = False
