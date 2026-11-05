#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Sep  4 18:59:16 2026

@author: lasse
"""

import json
import math

from pathlib import Path
# ALT: from markereinstellungen import lade_markereinstellungen, speichere_markereinstellungen

from PySide6.QtCore import Qt

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QCheckBox,
    QMessageBox,
    QHeaderView,
    QAbstractItemView
)


# NEU: Anzeigeoptionen direkt hier verwalten, zusammen mit dem Kalibrierfenster.
# NEU: Beide Markergruppen sind bei jedem Programmstart eingeschaltet.
_marker_einstellungen = dict(reflexion=True, periode=True)


def marker_zuruecksetzen():
    _marker_einstellungen.update(reflexion=True, periode=True)


def lade_markereinstellungen():
    return _marker_einstellungen.copy()


def speichere_markereinstellungen(reflexion, periode):
    # Nur für die laufende Sitzung merken; keine Datei anlegen.
    _marker_einstellungen.update(reflexion=bool(reflexion), periode=bool(periode))


# ALT: Bisherige dauerhafte Speicherung in Anzeige.json.
# def lade_markereinstellungen(datei="Anzeige.json"):
#     datei = Path(datei)
#     einstellungen = dict(reflexion=True, periode=True)
#     if datei.exists():
#         daten = json.loads(datei.read_text(encoding="utf-8"))
#         for name in einstellungen:
#             wert = daten.get(name, True)
#             if not isinstance(wert, bool):
#                 raise ValueError(f"Markeroption '{name}' muss true oder false sein.")
#             einstellungen[name] = wert
#     return einstellungen
# 
# 
# def speichere_markereinstellungen(reflexion, periode, datei="Anzeige.json"):
#     Path(datei).write_text(json.dumps(dict(reflexion=bool(reflexion), periode=bool(periode)),
#                                     indent=4) + "\n", encoding="utf-8")


class KalibrierFenster(QWidget):

    def __init__(self):

        super().__init__()

        self.setWindowTitle("Sensoren und Kalibrierung")

        self.resize(1100,750)

        self.datei = Path("Sensor.json")

        self.sensoren = {}

       
        # Hauptlayout
        layout = QVBoxLayout(self)

        
        # Sensortabelle
        sensor_label = QLabel("Sensoren")

        layout.addWidget(sensor_label)
        
        self.aktuelle_sensor_id = None

        self.sensor_tabelle = (QTableWidget())

        self.sensor_tabelle.setColumnCount(8)        

        self.sensor_tabelle.setHorizontalHeaderLabels([
            "Sensor-ID",
            "Hardware-Kanal",
            "Name",
            "Bezeichnung",
            "Seriennummer",
            "Typ / Einheit",
            "Rohrlänge [m]",
            "Aktiv"
        ])


        self.sensor_tabelle.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows )

        self.sensor_tabelle.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        self.sensor_tabelle.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch )

        layout.addWidget(self.sensor_tabelle,2)


        # Sensorbuttons
        sensor_button_layout = (QHBoxLayout())

        self.sensor_hinzufuegen_button = (QPushButton("Sensor hinzufügen"))

        self.sensor_loeschen_button = (QPushButton("Sensor löschen") )

        sensor_button_layout.addWidget(self.sensor_hinzufuegen_button)

        sensor_button_layout.addWidget(self.sensor_loeschen_button)

        sensor_button_layout.addStretch()

        layout.addLayout(sensor_button_layout)


        # Kalibrierpunkte        
        self.kalibrier_label = QLabel("Kalibrierpunkte")

        layout.addWidget(self.kalibrier_label)

        self.kalibrier_tabelle = (QTableWidget())

        self.kalibrier_tabelle.setColumnCount(2)

        self.kalibrier_tabelle.setHorizontalHeaderLabels([
            "Eingangswert",
            "Ausgangswert"
        ])


        self.kalibrier_tabelle.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        layout.addWidget(self.kalibrier_tabelle,2)


        # Kalibrierbuttons
        kalibrier_button_layout = (QHBoxLayout())

        self.punkt_hinzufuegen_button = (QPushButton("Kalibrierpunkt hinzufügen"))

        self.punkt_loeschen_button = ( QPushButton("Kalibrierpunkt löschen"))

        kalibrier_button_layout.addWidget(self.punkt_hinzufuegen_button)

        kalibrier_button_layout.addWidget(self.punkt_loeschen_button)

        kalibrier_button_layout.addStretch()

        layout.addLayout(kalibrier_button_layout)


        # NEU: Beide Verfahren unabhängig ein-/ausblenden (nur Darstellung).
        marker_layout = QHBoxLayout()
        self.reflexionsmarker_checkbox = QCheckBox("Reflexionsmarker anzeigen")
        self.periodenmarker_checkbox = QCheckBox("Periodenmarker anzeigen")
        self.reflexionsmarker_checkbox.setChecked(True)
        self.periodenmarker_checkbox.setChecked(True)
        marker_layout.addWidget(self.reflexionsmarker_checkbox)
        marker_layout.addWidget(self.periodenmarker_checkbox)
        marker_layout.addStretch()
        layout.addLayout(marker_layout)
        layout.addWidget(QLabel("Marker-Auswahl gilt nach dem Speichern für neue Auswertungen."))

        # Speichern
        speichern_layout = QHBoxLayout()

        speichern_layout.addStretch()

        self.speichern_button = (QPushButton("Änderungen speichern"))

        speichern_layout.addWidget(self.speichern_button)

        layout.addLayout(speichern_layout)


        # Signale
        self.sensor_tabelle.itemSelectionChanged.connect(self.sensor_ausgewaehlt)

        self.sensor_hinzufuegen_button.clicked.connect(self.sensor_hinzufuegen)

        self.sensor_loeschen_button.clicked.connect( self.sensor_loeschen)

        self.punkt_hinzufuegen_button.clicked.connect(self.punkt_hinzufuegen)

        self.punkt_loeschen_button.clicked.connect(self.punkt_loeschen)

        self.speichern_button.clicked.connect(self.speichern)

        self.laden()


    # JSON laden
    def laden(self):

        # NEU: Aktuelle Auswahl aus der laufenden Sitzung übernehmen.
        try:
            # ALT: marker = lade_markereinstellungen(self.datei.with_name("Anzeige.json"))
            marker = lade_markereinstellungen()
            self.reflexionsmarker_checkbox.setChecked(marker["reflexion"])
            self.periodenmarker_checkbox.setChecked(marker["periode"])
        except (OSError, ValueError, TypeError, AttributeError) as fehler:
            QMessageBox.warning(self, "Anzeigeoptionen", f"Markeroptionen konnten nicht geladen werden: {fehler}")

        if not self.datei.exists():

            QMessageBox.warning(
                self,
                "Datei fehlt",
                "Sensor.json wurde nicht gefunden."
            )

            return


        with open(self.datei, "r", encoding="utf-8") as f:

            self.sensoren = (json.load(f))

        self.sensor_tabelle_fuellen()


    # Sensortabelle
    def sensor_tabelle_fuellen(self):

        # Noch nicht gespeicherte Metadaten beim Hinzufügen/Löschen behalten.
        bearbeitet = {}
        for zeile in range(self.sensor_tabelle.rowCount()):
            id_item = self.sensor_tabelle.item(zeile, 0)
            if id_item is not None:
                bearbeitet[id_item.text()] = (
                    [self.sensor_tabelle.item(zeile, spalte).text()
                     for spalte in range(1, 7)],
                    self.sensor_tabelle.cellWidget(zeile, 7).isChecked()
                )
        vorher_blockiert = self.sensor_tabelle.blockSignals(True)
        self.sensor_tabelle.setRowCount(len(self.sensoren))

        for zeile, (sensor_id, sensor) in enumerate(self.sensoren.items()):

            # Sensor-ID
            id_item = QTableWidgetItem(sensor_id)
            id_item.setFlags(
                id_item.flags() & ~Qt.ItemFlag.ItemIsEditable
                )

            self.sensor_tabelle.setItem(zeile, 0, id_item)

            # Hardware-Kanal
            kanal = sensor.get("kanal", sensor.get("Kanal", ""))

            self.sensor_tabelle.setItem(
                zeile, 1, QTableWidgetItem(str(kanal))
                )

            # Sensorinformationen
            self.sensor_tabelle.setItem(
                zeile, 2,
                QTableWidgetItem(sensor.get("name", ""))
                )

            self.sensor_tabelle.setItem(
                zeile, 3,
                QTableWidgetItem(sensor.get("bezeichnung", ""))
                )

            self.sensor_tabelle.setItem(
                zeile, 4,
                QTableWidgetItem(str(sensor.get("seriennummer", "")))
                )

            typ_einheit = (
                f"{sensor.get('typ', '')} / "
                f"{sensor.get('einheit', '')}"
                )

            self.sensor_tabelle.setItem(
                zeile, 5, QTableWidgetItem(typ_einheit)
                )

            # Aktiv
            checkbox = QCheckBox()
            checkbox.setChecked(sensor.get("aktiv", True))
            
            self.sensor_tabelle.setItem(
                zeile, 6, QTableWidgetItem(str(sensor.get("rohrlaenge", 100.0)))
                )
            
            self.sensor_tabelle.setCellWidget(zeile, 7, checkbox)
            if sensor_id in bearbeitet:
                texte, aktiv = bearbeitet[sensor_id]
                for spalte, text in enumerate(texte, start=1):
                    self.sensor_tabelle.item(zeile, spalte).setText(text)
                checkbox.setChecked(aktiv)

        self.sensor_tabelle.clearSelection()
        self.sensor_tabelle.setCurrentCell(-1, -1)
        self.aktuelle_sensor_id = None
        self.kalibrier_tabelle.setRowCount(0)
        self.kalibrier_label.setText("Kalibrierpunkte")
        self.sensor_tabelle.blockSignals(vorher_blockiert)


    # Sensor auswählen
    def sensor_ausgewaehlt(self):

        zeile = (self.sensor_tabelle.currentRow())

        if zeile < 0:
            return

        kanal_item = (self.sensor_tabelle.item(zeile, 0))

        if kanal_item is None:
            return

        sensor_id = kanal_item.text()

        if sensor_id == self.aktuelle_sensor_id:
            return
        if not self.aktuelle_kalibrierung_sichern():
            vorher_blockiert = self.sensor_tabelle.blockSignals(True)
            for index in range(self.sensor_tabelle.rowCount()):
                if self.sensor_tabelle.item(index, 0).text() == self.aktuelle_sensor_id:
                    self.sensor_tabelle.setCurrentCell(index, 0)
                    self.sensor_tabelle.selectRow(index)
                    break
            self.sensor_tabelle.blockSignals(vorher_blockiert)
            return
        
        sensor = self.sensoren.get(sensor_id)

        if sensor is None:
            return


        self.aktuelle_sensor_id = sensor_id
        self.kalibrier_label.setText(f"Kalibrierpunkte: {sensor_id}")

        input_values = sensor.get("input_values",[])

        output_values = sensor.get( "output_values", [])

        anzahl = max(
            len(input_values),
            len(output_values)
        )

        self.kalibrier_tabelle.setRowCount(anzahl)

        for zeile in range(anzahl):

            input_wert = (input_values[zeile]
                if zeile < len(input_values) else ""
            )

            output_wert = (output_values[zeile]
                if zeile < len(output_values) else ""
            )

            self.kalibrier_tabelle.setItem(zeile, 0, QTableWidgetItem(str(input_wert)))

            self.kalibrier_tabelle.setItem(zeile, 1, QTableWidgetItem(str(output_wert)))


    # Kalibrierwerte aus Tabelle übernehmen
    def aktuelle_kalibrierung_sichern(self):

        sensor_id = self.aktuelle_sensor_id
        if sensor_id is None or sensor_id not in self.sensoren:
            return True

        input_values = []
        output_values = []

        for zeile in range(self.kalibrier_tabelle.rowCount()):

            input_item = (self.kalibrier_tabelle.item(zeile, 0) )

            output_item = (self.kalibrier_tabelle.item(zeile, 1))

            if (input_item is None or output_item is None):
                QMessageBox.warning(self, "Ungültiger Kalibrierpunkt",
                                    f"Sensor '{sensor_id}': Zeile {zeile + 1} ist unvollständig.")
                return False


            try:

                input_wert = float(input_item.text().replace(",", "."))

                output_wert = float( output_item.text().replace(",", "."))
                if not math.isfinite(input_wert) or not math.isfinite(output_wert):
                    raise ValueError

            except ValueError:

                QMessageBox.warning(self, "Ungültiger Kalibrierpunkt",
                                    f"Sensor '{sensor_id}': Zeile {zeile + 1} benötigt zwei endliche Zahlen.")
                return False


            input_values.append(input_wert)

            output_values.append(output_wert)

        if len(input_values) < 2 or any(
                rechts <= links for links, rechts in zip(input_values, input_values[1:])):
            QMessageBox.warning(self, "Ungültige Kalibrierung",
                                f"Sensor '{sensor_id}': Mindestens zwei Punkte mit streng steigenden Eingangswerten erforderlich.")
            return False

        self.sensoren[sensor_id]["input_values" ] = input_values

        self.sensoren[sensor_id]["output_values"] = output_values
        return True


    # Sensor hinzufügen
    def sensor_hinzufuegen(self):

        if not self.aktuelle_kalibrierung_sichern():
            return

        basis = "sensor"
        nummer = 1

        while (f"{basis}{nummer}" in self.sensoren):
            nummer += 1

        kanal = (f"{basis}{nummer}")

        self.sensoren[kanal] = {
            "kanal": -1,
            "rohrlaenge": 100.0,
            "name": kanal,
            "bezeichnung":"Neuer Sensor",
            "seriennummer": "",
            "typ": "druck",
            "aktiv": False,
            "einheit": "bar",
            "input_values": [0.0, 1.0],
            "output_values": [0.0, 1.0]
        }


        self.sensor_tabelle_fuellen()


    # Sensor löschen
    def sensor_loeschen(self):

        zeile = (self.sensor_tabelle.currentRow())

        if zeile < 0:

            QMessageBox.warning(
                self,
                "Kein Sensor ausgewählt",
                "Bitte zuerst einen Sensor auswählen."
            )

            return

        kanal = (self.sensor_tabelle.item(zeile, 0).text())

        antwort = (
            QMessageBox.question(
                self,
                "Sensor löschen",
                f"Sensor '{kanal}' wirklich löschen?"
            )
        )

        if (antwort != QMessageBox.StandardButton.Yes):
            return

        if kanal in self.sensoren:

            del self.sensoren[kanal]

        self.sensor_tabelle_fuellen()

        self.kalibrier_tabelle.setRowCount(0)

    # Kalibrierpunkt hinzufügen
    def punkt_hinzufuegen(self):

        zeile = (self.kalibrier_tabelle.rowCount())

        self.kalibrier_tabelle.insertRow(zeile)

        self.kalibrier_tabelle.setItem(
            zeile,
            0,
            QTableWidgetItem("0.0")
        )

        self.kalibrier_tabelle.setItem(
            zeile,
            1,
            QTableWidgetItem("0.0")
        )


    # Kalibrierpunkt löschen
    def punkt_loeschen(self):

        zeile = (self.kalibrier_tabelle.currentRow())

        if zeile < 0:

            QMessageBox.warning(
                self,
                "Kein Punkt ausgewählt",
                "Bitte zuerst einen Kalibrierpunkt auswählen."
            )

            return

        self.kalibrier_tabelle.removeRow(zeile)


    # Speichern
    def speichern(self):

        if not self.aktuelle_kalibrierung_sichern():
            return

        neue_sensoren = {}
        verwendete_kanaele = set()
        verwendete_namen = set()
        
        for zeile in range(self.sensor_tabelle.rowCount()):
            
            sensor_id = self.sensor_tabelle.item(zeile, 0).text().strip()
            kanal_text = self.sensor_tabelle.item(zeile, 1).text().strip()
            
            name = self.sensor_tabelle.item(zeile, 2).text().strip()
            if not name or name in verwendete_namen:
                QMessageBox.warning(self, "Ungültiger Sensorname",
                                    f"Sensor '{sensor_id}': Der Name muss ausgefüllt und eindeutig sein.")
                return
            
            verwendete_namen.add(name)
            bezeichnung = self.sensor_tabelle.item(zeile, 3).text().strip()
            seriennummer = self.sensor_tabelle.item(zeile, 4).text().strip()
            typ_einheit = self.sensor_tabelle.item(zeile, 5).text().strip()
            
            teile = typ_einheit.split("/", maxsplit=1)
            
            typ = teile[0].strip()
            einheit = teile[1].strip() if len(teile) > 1 else ""
            
            rohrlaenge_text = self.sensor_tabelle.item(zeile, 6).text().strip()
            try:
                rohrlaenge = float(rohrlaenge_text.replace(",", "."))
                if not __import__("math").isfinite(rohrlaenge) or rohrlaenge <= 0:
                    raise ValueError
            except ValueError:
                QMessageBox.warning(
                    self, "Ungültige Rohrlänge",
                    f"Sensor '{sensor_id}': Rohrlänge muss eine positive Zahl in Metern sein."
                )
                return
            
            checkbox = self.sensor_tabelle.cellWidget(zeile, 7)
            aktiv = checkbox.isChecked()
            
            # Hardware-Kanal prüfen
            try:
                kanal = int(kanal_text)
                
                if kanal < -1 or kanal > 7:
                    raise ValueError
                    
            except ValueError:
                        
                QMessageBox.warning(
                    self,
                    "Ungültiger Hardware-Kanal",
                    f"Sensor '{sensor_id}': "
                    "Der Hardware-Kanal muss zwischen 0 und 7 liegen."
                    )
                return
            
            if aktiv and kanal == -1:

                QMessageBox.warning(
                    self,
                    "Hardware-Kanal fehlt",
                    f"Sensor '{sensor_id}' ist aktiv, "
                    "hat aber keinen Hardware-Kanal."
                    )
                return
                    
            # Doppelte Kanäle bei aktiven Sensoren verhindern
            if aktiv:
                        
                if kanal in verwendete_kanaele:
                            
                    QMessageBox.warning(
                        self,
                        "Doppelter Hardware-Kanal",
                        f"Hardware-Kanal {kanal} ist mehrfach "
                        "aktiven Sensoren zugeordnet."
                        )
                    return
                        
                verwendete_kanaele.add(kanal)
                        
            # Bisherige Daten übernehmen
            alte_daten = self.sensoren.get(sensor_id, {}).copy()
                        
            # Alte Schreibweise entfernen
            alte_daten.pop("Kanal", None)
                        
            # Neue und bearbeitete Werte aktualisieren
            alte_daten.update({
                "kanal": kanal,
                "rohrlaenge": rohrlaenge,
                "name": name,
                "bezeichnung": bezeichnung,
                "seriennummer": seriennummer,
                "typ": typ,
                "aktiv": aktiv,
                "einheit": einheit
                })
                        
            neue_sensoren[sensor_id] = alte_daten
                        
        # Erst nach erfolgreicher Prüfung übernehmen
        self.sensoren = neue_sensoren
                        
        with open(self.datei, "w", encoding="utf-8") as f:
            json.dump(
                self.sensoren,
                f,
                indent=4,
                ensure_ascii=False
                )
                            
        # NEU: Anzeigeoptionen erst nach erfolgreicher Sensorprüfung speichern.
        try:
            speichere_markereinstellungen(
                self.reflexionsmarker_checkbox.isChecked(),
                # ALT: self.periodenmarker_checkbox.isChecked(), self.datei.with_name("Anzeige.json"))
                self.periodenmarker_checkbox.isChecked())
        except OSError as fehler:
            QMessageBox.warning(self, "Anzeigeoptionen", f"Sensoren gespeichert, Markeroptionen konnten nicht gespeichert werden: {fehler}")
            return

        QMessageBox.information(
            self,
            "Gespeichert",
            "Die Sensorkonfiguration wurde gespeichert."
            )
