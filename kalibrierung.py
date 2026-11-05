#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Aug  9 14:24:05 2026

@author: lasse
"""


import numpy as np
import json
from pathlib import Path


class SensorKalibrierung:
    

    def __init__(self, name, unit, input_values, output_values):
        

        self.name = name
        self.unit = unit

        self.input_values = np.array(input_values, dtype=float)
        self.output_values = np.array(output_values, dtype=float)

        if len(self.input_values) != len(self.output_values):   #Eingangs- und Ausgangstabelle müssen gleich viele Werte enthalten
            raise ValueError(
                f"Sensor '{name}': "
                "Eingangs- und Ausgangstabelle müssen gleich viele Werte enthalten." )

        if len(self.input_values) < 2:                            #die Kalibrierung benötigt mind zwei Werte.
            raise ValueError(
                f"Sensor '{name}': "
                "Mindestens zwei Kalibrierpunkte erforderlich." )

       
        if not np.all(np.diff(self.input_values) > 0):   # Prüfen, ob die Eingangswerte aufsteigend sortiert sind
            raise ValueError(
                f"Sensor '{name}': "
                "Eingangswerte müssen aufsteigend sortiert sein." )

    def calibrate(self, value):
        
        value = np.asarray( value, dtype=float)

        return np.interp(value, self.input_values, self.output_values )



class VerwaltungKali:               #Verwaltet mehrere Sensor-Kalibrierungen.
    

    def __init__(self):
        self.sensors = {}

    def add_sensor(self, sensor):       #Sensor hinzufügen NOTWENDIG?
        if not isinstance(sensor.name, str) or not sensor.name.strip():
            raise ValueError("Sensorname darf nicht leer sein.")
        if sensor.name != sensor.name.strip():
            raise ValueError("Sensorname darf keine äußeren Leerzeichen enthalten.")
        if sensor.name in self.sensors:
            raise ValueError(f"Sensor '{sensor.name}' existiert bereits.")

        self.sensors[sensor.name] = sensor

    def get_sensor(self, name):         #Sensor anhand seines Namens holen.

        if name not in self.sensors:
            raise KeyError(f"Sensor '{name}' ist nicht hinterlegt.")

        return self.sensors[name]

    

    def cali_dataframe(self, data, mapping):   #Kalibriert mehrere DataFrame-Spalten

        dataframe_kalibriert = (data.copy())
         
        

        for column, sensor_name in mapping.items():
            
            if column not in data.columns:
                continue

            sensor = self.get_sensor(sensor_name)

            if sensor is None:
                raise ValueError(
                    f"Kalibrierung '{sensor_name}' "
                    f"für Spalte '{column}' "
                    "nicht gefunden."
                )
                
            dataframe_kalibriert[column] = sensor.calibrate(data[column])

        return dataframe_kalibriert
    
    
    # JSON laden

def lade_sensordaten(datei="Sensor.json"):

        datei = Path(datei)

        if not datei.exists():

            raise FileNotFoundError(
                f"Sensordatei nicht gefunden: "
                f"{datei.resolve()}"
                )

        with open(
                datei,
                "r",
                encoding="utf-8"
                ) as f:

            sensor_daten = json.load(f)

        return sensor_daten



# Kalibrierverwaltung aus JSON erzeugen

def lade_sensoren(datei="Sensor.json"):

        sensor_daten = lade_sensordaten(datei)

        verwaltung = VerwaltungKali()

        mapping = {}

        namen = set()
        for sensor_id, daten in sensor_daten.items():
            name = daten.get("name")
            if not isinstance(name, str) or not name.strip() or name != name.strip():
                raise ValueError(f"Sensor '{sensor_id}': Ungültiger Sensorname.")
            if name in namen:
                raise ValueError(f"Sensor '{sensor_id}': Sensorname '{name}' ist mehrfach vergeben.")
            namen.add(name)

        for sensor_id, daten in sensor_daten.items():

        # Inaktive Sensoren nicht verwenden
            if not daten.get("aktiv", True ):
                continue
            
            kanal = daten.get("kanal")

            if not isinstance(kanal, int) or not 0 <= kanal <= 7:
                raise ValueError(
                    f"Sensor '{sensor_id}': "
                    "Ungültiger oder fehlender Hardware-Kanal."
                    )

            sensor = SensorKalibrierung(
                name=daten["name"],
                unit=daten["einheit"],
                input_values= daten["input_values"],
                output_values= daten["output_values"])

            verwaltung.add_sensor(sensor)

            mapping[sensor_id] = daten["name"]

        return (verwaltung,mapping,sensor_daten)
