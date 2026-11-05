#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Sep 17 09:55:26 2026

@author: lasse
"""

"""
Testprogramm für die Kommunikation mit der Gantner Q.station.

Prüft:
- Verbindung zur Q.station
- Abtastrate
- Anzahl und Namen der Kanäle
- Lesen eines Datenblocks
- Form und erste Messwerte des Datenblocks
- wird stand 24.09. nicht mehr gebraucht 
"""

# NEU: Direkter Start aus dem Diagnoseordner verwendet die Projektmodule/-daten.
import sys as _sys
from pathlib import Path as _Path
_projektordner = _Path(__file__).resolve().parent.parent
if str(_projektordner) not in _sys.path:
    _sys.path.insert(0, str(_projektordner))
if __name__ == "__main__":
    import os as _os
    _os.chdir(_projektordner)

import numpy as np
import ginsapy.giutility.highspeedport as highspeedport


GANTNER_IP = "169.254.9.202"
BUFFER_INDEX = 0


def main():

    verbindung = highspeedport.HighSpeedPortClient()
    verbindung.bufferindex = BUFFER_INDEX

    try:
        
        # Verbindung herstelle
        print(f"Verbinde mit Q.station unter {GANTNER_IP} ...")

        verbindung.init_connection(GANTNER_IP)

        print("Verbindung hergestellt.\n")


        # Geräteinformationen
        abtastrate = verbindung.read_sample_rate()
        kanalzahl = verbindung.read_channel_count()

        print("=== Q.station ===")
        print(f"IP-Adresse:  {GANTNER_IP}")
        print(f"Abtastrate:  {abtastrate} Hz")
        print(f"Kanalzahl:   {kanalzahl}")


        # Kanalnamen
        print("\n=== Kanäle ===")

        kanalnamen = []

        for index in range(kanalzahl):
            name = verbindung.read_index_name(index)
            kanalnamen.append(name)

            print(f"{index}: {name}")


        # Buffer starten
        print("\n=== Datenblock lesen ===")

        buffer_generator = verbindung.yield_buffer()

        datenblock = next(buffer_generator)

        datenblock = np.asarray(datenblock)


        # Informationen über den Datenblock
        print(f"Typ:    {type(datenblock)}")
        print(f"Shape:  {datenblock.shape}")
        print(f"Dtype:  {datenblock.dtype}")


        # Erste Messwerte anzeigen
        print("\n=== Erste 5 Zeilen ===")

        np.set_printoptions(precision=6, suppress=True, linewidth=200)

        print(datenblock[:5])

      
        # Zuordnung Spalten zu Kanalnamen
        print("\n=== Spaltenzuordnung ===")

        if datenblock.ndim == 2:

            spaltenzahl = datenblock.shape[1]

            for index in range(spaltenzahl):

                if index < len(kanalnamen):
                    name = kanalnamen[index]
                else:
                    name = "unbekannt"

                print(f"Spalte {index}: {name}")

        else:
            print("Datenblock ist nicht zweidimensional: " f"Shape = {datenblock.shape}")

    except StopIteration:
        print("\nFEHLER: Der Buffer hat keine Daten geliefert." )

    except Exception as e:
        print( f"\nFEHLER: {type(e).__name__}: {e}" )

    finally:
        print("\nVerbindung wird geschlossen ...")

        try:
            verbindung.close_connection()
        except Exception:
            pass

        print("Fertig.")


if __name__ == "__main__":
    main()