#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Aug  26 16:15:18 2026

@author: lasse
"""

import os, sys, math
import json
import numpy as np
from uuid import uuid4
import pandas as pd
import plotly.graph_objects as go  
from datetime import datetime
from pathlib import Path

#from Sensor import kalibrierung
from Analyse import SignalAnalyse
from kalibrierung import (lade_sensoren)
from gantner import GantnerMessung
# ALT: from markereinstellungen import lade_markereinstellungen
from kalibrierFenster import lade_markereinstellungen

# NEU: Rohdatensicherung aus rohdaten.py hierher verschoben.
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


# ALT: def durchführungAnalyse(datenblock, abtastrate, remote_modus=False):
# NEU: Bereits während der Aufnahme gesicherte Rohdatei berücksichtigen.
def durchführungAnalyse(datenblock, abtastrate, remote_modus=False, rohdatei=None):
    

    speicherort = Path("./Ergebnisse")
    speicherort.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
    # NEU: Nur die Anzeige steuern; beide Berechnungen bleiben aktiv.
    marker_einstellungen = lade_markereinstellungen()
    

    (
        kalibrierung,
        mapping,
        sensor_daten
    ) = lade_sensoren()

 

    # Datenblock prüfen

    if datenblock is None:
       raise ValueError("Keine Messdaten vorhanden.")

    if datenblock.ndim != 2:
       raise ValueError(f"Ungültiger Datenblock: {datenblock.shape}")

    if datenblock.shape[1] != 9:
       raise ValueError(f"Q.station liefert unerwartete Kanalzahl: "f"{datenblock.shape[1]}")

    if abtastrate <= 0:
       raise ValueError(f"Ungültige Abtastrate: {abtastrate}" )

    print(
       f"Auswertung von {len(datenblock)} Samples | "
       f"{abtastrate:.0f} Hz | "
       f"{len(datenblock) / abtastrate:.3f} s"
   )


   # Sensoren den Gantner-Kanälen zuordnen

    data = pd.DataFrame()

    for sensor_id, einstellungen in sensor_daten.items():
        
        #inaktive sensoren überspringen
        if not einstellungen.get("aktiv", True):
            continue
        
        #Hardware-Kanal aus der json-Datei
        kanal = int(einstellungen["kanal"])
        
        #Spalte 0 enthält Zeitstempel
        gantner_spalte = kanal + 1

        if kanal < 0 or gantner_spalte >= datenblock.shape[1]:
            raise ValueError(
                f"Sensor '{sensor_id}' verwendet "
                f"den ungültigen Hardware-Kanal {kanal}."
                )

        # Messwerte unter der Sensor-ID speichern
        data[sensor_id] = datenblock[:, gantner_spalte]
        
        print(
        f"Sensor {sensor_id}: "
        f"Hardware-Kanal {kanal}, "
        f"DataFrame-Spalte hinzugefügt."
        )
 
    # Relative Zeitachse
    dt = 1.0 / abtastrate

    data.insert(0, "time", data.index.to_numpy() * dt)
 
    
    # Rohdaten speichern
    
    # Rohdaten nur bei echter Q.station-Messung speichern    
    if not remote_modus and rohdatei is None:
    
        filename_raw = speicherort / f"apmbRaw_{timestamp}.csv"
    
        # Ursprünglichen Datenblock unverändert speichern:
        # Spalte 0 = Timestamp
        # Spalten 1–8 = Hardware-Kanäle
        pd.DataFrame(datenblock).to_csv(
            filename_raw,
            sep="\t",
            decimal=",",
            header=False,
            index=False,
            float_format="%.10f"
        )
    
        print(f"Rohdaten gespeichert: {filename_raw}")
    

 
    # Kalibrierung
    daten_kalibriert = ( kalibrierung.cali_dataframe( data, mapping))
    
    # print("DEBUG Rohdaten-Spalten:", data.columns.tolist())
    # print("DEBUG Kalibrierte Spalten:", daten_kalibriert.columns.tolist())
    # print("DEBUG Mapping:", mapping)
    
    # Aktive Sensoren
    aktive_sensoren = [kanal
        for kanal, daten in sensor_daten.items()
        if daten.get("aktiv", True)
    ]
    #print("DEBUG Aktive Sensoren:", aktive_sensoren)

    aktive_drucksensoren = [kanal
        for kanal, daten in sensor_daten.items()
        if ( daten.get("aktiv", True) and daten.get("typ") == "druck")
    ]

    aktive_durchflusssensoren = [kanal
        for kanal, daten in sensor_daten.items()
        if (daten.get("aktiv", True) and daten.get("typ") == "durchfluss")
    ]

    if not aktive_drucksensoren:
        raise ValueError("Keine aktiven Drucksensoren in sensoren.json gefunden.")

    
    # Nur aktive Sensoren speichern
    spalten_speichern = ["time" ] + aktive_sensoren

    daten_kalibriert_aktiv = (daten_kalibriert[ spalten_speichern ])

    filename_data = (speicherort / f"apmbData_{timestamp}.csv")

    daten_kalibriert_aktiv.to_csv(filename_data,index=False)

    
    # Signalanalyse
    ergebnisse = {}

    for sensor in aktive_drucksensoren:

        analysieren = SignalAnalyse(
            daten_kalibriert_aktiv["time"],
            daten_kalibriert_aktiv[sensor]
        )

        ergebnisse[sensor] = {
            "frequency": analysieren.frequenz(),

            "amplitude": analysieren.amplitude(),

            "maximum": analysieren.maximum(),

            "minimum": analysieren.minimum()
        }

    
    # Druckstoßanalyse
    druckstoesse = {}

    for druck_sensor in aktive_drucksensoren:

        analyse_druck = SignalAnalyse(
            daten_kalibriert_aktiv["time"],
            daten_kalibriert_aktiv[druck_sensor]
            )

        druckstoss = analyse_druck.schallgeschwindigkeit(
            rohrlaenge=float(
                sensor_daten[druck_sensor].get("rohrlaenge", 100.0)
                )
        )

     # Ergebnis für diesen Sensor merken
        druckstoesse[druck_sensor] = druckstoss



        if druckstoss is not None:

            # NEU: Phasengrenzen, Gesamtamplitude und Kandidatenstatus dokumentieren.
            for key in ("t_maximum", "t_minimum", "druck_maximum", "druck_minimum",
                        "reflexions_amplitude", "mindest_amplitude", "gradient_reflexion",
                        "phasen_umkehrschwelle", "methode", "status", "anzahl_kandidaten"):
                ergebnisse[druck_sensor][key] = druckstoss[key]

            ergebnisse[druck_sensor]["schallgeschwindigkeit"] = druckstoss["schallgeschwindigkeit"]

            ergebnisse[druck_sensor]["laufzeit"] = druckstoss["laufzeit"]

            ergebnisse[druck_sensor]["t_start"] = druckstoss["t_start"]

            ergebnisse[druck_sensor]["t_reflexion"] = druckstoss["t_reflexion"]
        
        else:

            # NEU: Fehlende Erkennung ausdrücklich kennzeichnen.
            ergebnisse[druck_sensor]["status"] = "Kein Reflexionskandidat"

            ergebnisse[druck_sensor]["schallgeschwindigkeit" ] = None

            ergebnisse[druck_sensor]["laufzeit"] = None

            ergebnisse[druck_sensor]["t_start" ] = None

            ergebnisse[druck_sensor]["t_reflexion" ] = None




    # Die sensorbezogenen Reflexionslängen (z. B. p2: 50 m) gelten hier nicht.
    perioden_rohrlaenge = float(sensor_daten.get("p1", {}).get("rohrlaenge", 100.0))
    perioden_referenz = None
    if "p1" in aktive_drucksensoren:
        perioden_referenz = SignalAnalyse(
            daten_kalibriert_aktiv["time"], daten_kalibriert_aktiv["p1"]
        ).perioden_referenzzeit()

    perioden_fenster = []
    #Darstellungsdaten unabhängig von den Reflexionsmarkierungen halten
    perioden_markierungen = {}
    perioden_punkte = []

    for sensor in aktive_drucksensoren:
        periode = SignalAnalyse(
            daten_kalibriert_aktiv["time"], daten_kalibriert_aktiv[sensor]
        ).schallgeschwindigkeit_periode(
            rohrlaenge=perioden_rohrlaenge, referenzzeit=perioden_referenz)
        
        if periode["markierungen"] is not None:
            markierung = periode["markierungen"]
            perioden_markierungen[sensor] = markierung

            for typ in ("maxima", "minima"):
                perioden_punkte.extend({"Sensor": sensor, "Typ": typ,
                                        "Fenster_start": markierung["start"],
                                        "Fenster_ende": markierung["ende"],
                                        "Trendgrad": markierung["trendgrad"], **punkt}
                                       for punkt in markierung[typ])
        ergebnisse[sensor].update(
            schallgeschwindigkeit_periode=periode["schallgeschwindigkeit"],
            periode_s=periode["periode"], periode_min_s=periode["periode_min"],
            periode_max_s=periode["periode_max"], perioden_rohrlaenge=perioden_rohrlaenge,
            perioden_fenster_geprueft=periode["fenster_geprueft"],
            perioden_fenster_bestaetigt=periode["fenster_bestaetigt"],
            perioden_begruendung=periode["grund"])
        
        perioden_fenster.extend({"Sensor": sensor, **fenster} for fenster in periode["fenster"])

    # NEU: Dritte, unabhängige Methode für das Paar p1 (Ventil) → p4 (oben).
    # Laut Versuchsgeometrie beträgt dieser Weg 100 m, entsprechend p1–Oberwasser.
    # Ein explizites abstand_zu_p1 bei p4 kann diese Strecke bei Bedarf überschreiben.
    for sensor in aktive_drucksensoren:
        ergebnisse[sensor]["schallgeschwindigkeit_differenz_p1_p4"] = None
    differenz = dict(schallgeschwindigkeit=None, grund="p1 und p4 müssen aktive Drucksensoren sein.")
    if "p1" in aktive_drucksensoren and "p4" in aktive_drucksensoren:
        differenz = SignalAnalyse(
            daten_kalibriert_aktiv["time"], daten_kalibriert_aktiv["p1"]
        ).schallgeschwindigkeit_differenz(
            SignalAnalyse(daten_kalibriert_aktiv["time"], daten_kalibriert_aktiv["p4"]),
            sensorabstand=float(sensor_daten["p4"].get("abstand_zu_p1", perioden_rohrlaenge)))
    for sensor in ("p1", "p4"):
        if sensor in ergebnisse:
            ergebnisse[sensor].update(
                schallgeschwindigkeit_differenz_p1_p4=differenz["schallgeschwindigkeit"],
                differenz_p1_p4_json=json.dumps(differenz, ensure_ascii=False, allow_nan=False))

    # ALT: Separate Fensterdatei; jetzt in signal_analysis zusammengeführt.
    # if perioden_fenster:
    #     pd.DataFrame(perioden_fenster).to_csv(
    #         speicherort / f"periodenanalyse_{timestamp}.csv", index=False)
        
    # ALT: Separate Punktdatei.
    # if perioden_punkte:
    #     pd.DataFrame(perioden_punkte).to_csv(
    #         speicherort / f"periodenpunkte_{timestamp}.csv", index=False)

    #Alle ausreichenden Abfallphasen zur Prüfung der Auswahl speichern.
    kandidaten_zeilen = []
    for sensor, druckstoss in druckstoesse.items():
        if druckstoss is None:
            continue
        for nummer, kandidat in enumerate(druckstoss["kandidaten"], start=1):
            kandidaten_zeilen.append({"Sensor": sensor, "Kandidat": nummer,
                                      "ausgewaehlt": nummer == 1, **kandidat})
            
    # ALT: Separate Kandidatendatei.
    # if kandidaten_zeilen:
    #     pd.DataFrame(kandidaten_zeilen).to_csv(
    #         speicherort / f"reflexionskandidaten_{timestamp}.csv", index=False)

    # Ergebnisse Konsole
    for sensor, result in ergebnisse.items():

        print(
            f"{sensor}: "
            f"Frequenz = {result['frequency']:.2f} Hz | "
            f"Amplitude = {result['amplitude']:.4f} bar"
        )

    
    # Ergebnisse speichern
    ergebnisse_dataframe = (pd.DataFrame.from_dict(ergebnisse, orient="index"))

    ergebnisse_dataframe.index.name = "Sensor"

    # NEU: Alle bisherigen Detailzeilen vollständig beim zugehörigen Sensor ablegen.
    # JSON-Listen innerhalb der CSV erhalten beliebig viele Fenster/Punkte/Kandidaten,
    # ohne Sensorergebnisse zu vervielfachen oder Einträge abzuschneiden. Leer = [].
    for spalte, detailzeilen in (
            ("periodenanalyse_json", perioden_fenster),
            ("periodenpunkte_json", perioden_punkte),
            ("reflexionskandidaten_json", kandidaten_zeilen)):
        ergebnisse_dataframe[spalte] = [
            json.dumps([zeile for zeile in detailzeilen if zeile["Sensor"] == sensor],
                       ensure_ascii=False, allow_nan=False)
            for sensor in ergebnisse_dataframe.index
        ]

    ergebnisse_file = (speicherort / f"signal_analysis_{timestamp}.csv")

    ergebnisse_dataframe.to_csv(ergebnisse_file)

    print(ergebnisse_file)

    
    # Plotly
    fig = go.Figure()

    
    # Drucksensoren
    for sensor in aktive_drucksensoren:

        fig.add_trace(
            go.Scatter(
                x=daten_kalibriert_aktiv["time"],
                y=daten_kalibriert_aktiv[sensor],
                mode="lines",
                name=sensor,
                yaxis="y"
            )
        )

   
    # NEU: Genau die beiden für die Differenzmethode verwendeten Gradientenzeiten.
    # Die Höhe wird auf der angezeigten Druckkurve abgelesen, nicht im Gradientenplot.
    if differenz["schallgeschwindigkeit"] is not None:
        differenzzeiten = [differenz["t_p1"], differenz["t_p4"]]
        differenzdruecke = [
            float(np.interp(differenz[f"t_{sensor}"], daten_kalibriert_aktiv["time"],
                            daten_kalibriert_aktiv[sensor])) for sensor in ("p1", "p4")]
        fig.add_trace(go.Scatter(
            x=differenzzeiten, y=differenzdruecke, mode="markers",
            marker=dict(symbol="star", size=14, color=["#6a1b9a", "#00695c"],
                        line=dict(width=1, color="black")),
            name="Differenzmethode P1_p4", legendgroup="differenz_p1_p4",
            text=[
                f"{sensor}: erster positiver Gradientengipfel"
                f"<br>Gradient: {differenz[f'gradient_{sensor}']:.3f} bar/s"
                f"<br>Laufzeit p1 → p4: {differenz['laufzeit']:.4f} s"
                f"<br>Sensorabstand: {differenz['sensorabstand']:.2f} m"
                f"<br>Geschwindigkeit: {differenz['schallgeschwindigkeit']:.2f} m/s"
                for sensor in ("p1", "p4")],
            hovertemplate="%{text}<br>Zeit: %{x:.4f} s<br>Druck: %{y:.4f} bar<extra></extra>"))

    #Extrema eines bestätigten Beispielfensters am ursprünglichen Druckverlauf.
    # Die Extrema stammen aus dem trendbereinigten Signal; die y-Werte sind Rohkurvenwerte.
    for sensor, fenster in perioden_markierungen.items():
        if not marker_einstellungen["periode"]:
            continue

        fig.add_vrect(x0=fenster["start"], x1=fenster["ende"],
                      fillcolor="lightgreen", opacity=0.06, line_width=0)
        
        for typ, symbol, bezeichnung in (("maxima", "circle", "Maxima"),
                                         ("minima", "triangle-down", "Minima")):
            
            punkte = fenster[typ]
            zeiten = [p["zeit"] for p in punkte]
            abstaende = [None] + [zeiten[i] - zeiten[i-1] for i in range(1, len(zeiten))]
            hover = [
                f"{sensor}: Periode – {bezeichnung}<br>t = {p['zeit']:.4f} s"
                f"<br>Druck = {p['druck']:.4f} bar"
                + (f"<br>Abstand zum vorherigen Punkt = {abstand:.4f} s" if abstand is not None else "")
               #+ "<br>Extremum nach Trendentfernung; bestätigtes Beispielfenster"
               #"<br>Tabellenwert: Median der Autokorrelationsperioden mehrerer Fenster"
                for p, abstand in zip(punkte, abstaende)
            ]

            fig.add_trace(go.Scatter(
                x=zeiten, y=[p["druck"] for p in punkte], mode="markers",
                marker=dict(symbol=symbol, size=10, line=dict(width=1, color="black")),
                name=f"{sensor}: Periode – {bezeichnung}",
                legendgroup=f"periode_{sensor}", text=hover, hovertemplate="%{text}<extra></extra>"))

    # Durchfluss
    for sensor in aktive_durchflusssensoren:

        fig.add_trace(
            go.Scatter(
                x=daten_kalibriert_aktiv["time"],
                y=daten_kalibriert_aktiv[sensor],
                mode="lines",
                name=sensor,
                yaxis="y2",
                line=dict(
                    dash="dot",
                    width=2
                )
            )
        )

    # Druckstoß-Markierungen alle Drucksensoren
    for sensor, druckstoss in druckstoesse.items():

        if druckstoss is None or not marker_einstellungen["reflexion"]:
            continue

        # Bewertete Abfallphase und ihre Randpunkte sichtbar machen.
        fig.add_vrect(x0=druckstoss["t_maximum"], x1=druckstoss["t_minimum"],
                      fillcolor="lightblue", opacity=0.15, line_width=0)
        fig.add_trace(go.Scatter(
            x=[druckstoss["t_maximum"], druckstoss["t_minimum"]],
            y=[druckstoss["druck_maximum"], druckstoss["druck_minimum"]],
            mode="markers", marker=dict(symbol="diamond", size=8),
            name=f"{sensor}:"   #Abfallphase Maximum/Minimum"
           ))

        fig.add_vline(
            x=druckstoss["t_start"],
            line_dash="dash",
            )
    
        fig.add_vline(
            x=druckstoss["t_reflexion"],
            line_dash="dash",
            )

        # Zeitangaben gezielt per Hover statt überlappender Beschriftungen.
        reflexionszeiten = [druckstoss["t_start"], druckstoss["t_reflexion"]]
        fig.add_trace(go.Scatter(
            x=reflexionszeiten,
            y=np.interp(reflexionszeiten, daten_kalibriert_aktiv["time"],
                        daten_kalibriert_aktiv[sensor]),
            mode="markers", marker=dict(symbol="x", size=10),
            name=f"{sensor}: Stoßbeginn/Reflexion",
            text=[f"{sensor}: ", f"{sensor}:"], #text=[f"{sensor}: Stoßbeginn t₀", f"{sensor}: Reflexionskandidat t₁"],
            hovertemplate="%{text}<br>Zeit: %{x:.4f} s<br>Druck: %{y:.4f} bar<extra></extra>"))



    # Ergebnistabelle
    if ergebnisse:

        tabelle = (pd.DataFrame.from_dict( ergebnisse, orient="index"))

        tabelle.index.name = "Sensor"
        tabelle = tabelle.reset_index()

        if ("schallgeschwindigkeit" not in tabelle.columns):
            tabelle["schallgeschwindigkeit"] = float("nan")

        schallgeschwindigkeit_anzeige = (
            tabelle[
                "schallgeschwindigkeit"
            ].apply(
                lambda x:
                    f"{x:.2f}"
                    if pd.notna(x)
                    else ""
            )
        )

        # Fehlende/uneindeutige Periodenwerte als leere Tabellenzellen anzeigen.
        perioden_anzeige = tabelle["schallgeschwindigkeit_periode"].apply(
            lambda x: f"{x:.2f}" if pd.notna(x) else "")
        differenz_anzeige = tabelle["schallgeschwindigkeit_differenz_p1_p4"].apply(
            lambda x: f"{x:.2f}" if pd.notna(x) else "")

        fig.add_trace(
            go.Table(
                # Mehr Platz für die beiden langen Geschwindigkeitsüberschriften.
                # ALT: columnwidth=[.7, .9, 1, 1, 1, 1.5, 1.7],
                columnwidth=[.7, .9, 1, 1, 1, 1.5, 1.7, 1.5],
                header=dict(
                    height=60,
                    font=dict(size=12),
                    values=[
                        "Sensor",
                        "Frequenz [Hz]",
                        "Amplitude [bar]",
                        "Maximum [bar]",
                        "Minimum [bar]",
                        "Schallgeschwindigkeit [m/s]",
                        # ALT: "Schallgeschwindigkeit nach Periode [m/s]"
                        "Schallgeschwindigkeit nach Periode [m/s]",
                        "Differenzmethode P1_p4<br>[m/s]"
                    ]
                ),

                cells=dict(
                    height=28,
                    font=dict(size=12),
                    values=[
                        tabelle["Sensor"],
                        tabelle["frequency"].round(2),
                        tabelle["amplitude"].round(4),
                        tabelle["maximum"].round(4),
                        tabelle["minimum"].round(4),
                        schallgeschwindigkeit_anzeige,
                        # ALT: perioden_anzeige
                        perioden_anzeige,
                        differenz_anzeige
                    ]
                ),

                domain=dict(
                    x=[0, 1],
                    y=[0, 0.30]
                )
            )
        )

   
    # Titel
    titel = "Druck- und Durchflussverlauf"

    fig.update_layout(title=titel,
        
        xaxis=dict(title="Zeit [s]", domain=[0, .72], automargin=True),

        yaxis=dict(title="Druck [bar]", domain=[0.44, 1], automargin=True),
        
        yaxis2=dict(title=dict(text="Durchfluss [l/min]", standoff=12),
                    overlaying="y", side="right", anchor="free", position=.74,
                    automargin=True),
        legend=dict(x=.80, xanchor="left", y=1, yanchor="top", font=dict(size=11)),

        margin=dict(l=70, r=40, t=70, b=35),

        height=max(900, int((60 + 28 * len(ergebnisse)) / .30 + 120)),
        
        hovermode="x unified"
        )

   
    # HTML speichern
    html_datei = (speicherort / f"druck_durchfluss_{timestamp}.html")

    fig.write_html(html_datei)

    
    # Rückgabe an GUI
    return (daten_kalibriert_aktiv, ergebnisse, html_datei)

