#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Aug 20 12:07:03 2026

@author: lasse
"""

import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.signal import correlate, find_peaks, resample_poly


#Periodenfenster
def periodenfenster(zeit, signal, trendgrad=1):
    """ACF-Kandidat und Extrema-Abstände; keine physikalische Wellenzuordnung.

    Diagnosegrenzen: mindestens drei Perioden im Fenster, ACF >= 0.2,
    Prominenz >= 0.05 und vorheriger negativer ACF-Abschnitt.
    Nicht passende Fälle liefern keinen Periodenkandidaten.
    """
    zeit = np.asarray(zeit, dtype=float)
    signal = np.asarray(signal, dtype=float)

    if zeit.ndim != 1 or zeit.shape != signal.shape or len(zeit) < 100:
        raise ValueError("Gleich lange eindimensionale Zeit- und Messarrays erforderlich.")
    
    if not np.all(np.isfinite(zeit)) or not np.all(np.isfinite(signal)):
        raise ValueError("Zeit und Signal müssen endlich sein.")
    
    dt = float(np.median(np.diff(zeit)))

    if dt <= 0 or not np.allclose(np.diff(zeit), dt, rtol=.01, atol=dt * 1e-6):
        raise ValueError("Gleichmäßige, streng steigende Zeitachse erforderlich.")
    
    faktor = max(1, round(1 / dt / 1000))

    # Lineare Randfortsetzung verhindert künstliche Sprünge gegen Null am Fensterrand.
    y = resample_poly(signal, 1, faktor, padtype="line")

    t = np.arange(len(y)) * dt * faktor

    trend = np.polynomial.polynomial.polyval(
        t, np.polynomial.polynomial.polyfit(t, y, trendgrad))
    
    z = y - trend

    basis = dict(T_acf_s=None, ACF=None, T_extrema_s=None, Intervalle=0,
                 CV_extrema=None, signal_spanne_bar=float(np.ptp(y)))
    
    if np.dot(z, z) <= 1e-12 * max(float(np.dot(y, y)), 1):
        return basis, (t, z, np.zeros(len(z)), np.array([], dtype=int))
    
    acf = correlate(z, z, mode="full", method="fft")[len(z)-1:]
    acf /= acf[0]

    peaks, _ = find_peaks(acf, prominence=.05)
    peaks = [p for p in peaks if .05 <= t[p] <= t[-1] / 3
             and acf[p] >= .2 and np.min(acf[:p]) < 0]
    
    if not peaks:
        return basis, (t, z, acf, np.array([], dtype=int))
    
    index = peaks[0]

    periode = float(t[index])

    basis.update(T_acf_s=periode, ACF=float(acf[index]))

    glatt = gaussian_filter1d(z, max(1, .01 / (dt * faktor) / 2.355))

    extrema, _ = find_peaks(glatt, prominence=.05 * np.ptp(glatt),
                            distance=max(1, round(.6 * periode / (dt * faktor))))
    
    abstaende = np.diff(t[extrema])

    if len(abstaende):
        basis.update(T_extrema_s=float(np.median(abstaende)), Intervalle=len(abstaende),
                     CV_extrema=float(np.std(abstaende) / np.mean(abstaende))

                     if len(abstaende) > 1 else None)
        
    return basis, (t, z, acf, extrema)



class SignalAnalyse:

    def __init__(self, time, signal):
        self.time = np.asarray(time)
        self.signal = np.asarray(signal)

        self.dt = np.mean(np.diff(self.time))       #Durchschnitt der zeitschritte. Ist ergänzend aber in meinem fall immer gleich
        self.sampling_frequency = 1 / self.dt       #gleiches für frequenz

        
    def fft_berechnen(self):

        signal_centered = (self.signal - np.mean(self.signal))     #Signal um Mittelwert zentrieren

        fft_werte = np.fft.rfft(signal_centered)

        frequenz_berechnet = np.fft.rfftfreq(len(signal_centered), d=self.dt)

        amplitude_berechnet = ( 2 / len(signal_centered)) * np.abs(fft_werte)

        amplitude_berechnet[0] = 0

        return frequenz_berechnet, amplitude_berechnet


    def frequenz(self):

        frequenz_berechnet, amplitude_berechnet = self.fft_berechnen()

        index = np.argmax(amplitude_berechnet)

        return frequenz_berechnet[index]


    def amplitude(self):

        return (self.signal.max() - self.signal.min() ) / 2
    
    
    def maximum(self):

        return self.signal.max()


    def minimum(self):

        return self.signal.min()
    
    def druckgradient(self):

        return np.gradient(self.signal,self.time)

    # NEU: Dritte Methode: Laufzeit des ersten Druckgradienten von p1 nach p4.
    def schallgeschwindigkeit_differenz(self, zweiter_sensor, sensorabstand,
                                      glaettung_ms=3.0, prueffenster_ms=50.0,
                                      min_druckanstieg=0.03):
        """c = Abstand / (t_zweiter - t_erster), ohne Reflexionsfaktor 2.

        Erster ausreichend deutlicher positiver Gradientengipfel je Sensor.
        Ein Medianvergleich vor/nach dem Gipfel unterdrückt kleine Störspitzen.
        Annahme: Beide Gipfel gehören zur selben vom Ventil ausgehenden Welle.
        """
        zeit = np.asarray(self.time, dtype=float)
        if (zeit.ndim != 1 or len(zeit) < 100 or not np.all(np.isfinite(zeit))
                or not np.all(np.diff(zeit) > 0)):
            raise ValueError("Mindestens 100 endliche, streng aufsteigende Zeitwerte erforderlich.")
        
        if not np.array_equal(zeit, zweiter_sensor.time):
            raise ValueError("Die Sensoren benötigen dieselbe Zeitachse.")
        
        for wert in (sensorabstand, glaettung_ms, prueffenster_ms, min_druckanstieg):
            if not np.isfinite(wert) or wert <= 0:
                raise ValueError("Sensorabstand und Analyseparameter müssen positiv und endlich sein.")
            
        dt = float(np.median(np.diff(zeit)))

        if not np.allclose(np.diff(zeit), dt, rtol=.01, atol=dt * 1e-6):
            raise ValueError("Die Zeitachse muss gleichmäßig abgetastet sein.")
        
        fenster = max(5, round(prueffenster_ms / 1000 / dt))

        r = dict(schallgeschwindigkeit=None, laufzeit=None, sensorabstand=float(sensorabstand),
                 t_p1=None, t_p4=None, gradient_p1=None, gradient_p4=None,
                 druckanstieg_p1=None, druckanstieg_p4=None,
                 grund="Kein ausreichend deutlicher erster Gradient an beiden Sensoren.")

        def erster_gradient(analyse):
            signal = np.asarray(analyse.signal, dtype=float)
            if signal.shape != zeit.shape or not np.all(np.isfinite(signal)):
                raise ValueError("Beide Messsignale müssen endlich sein und zur Zeitachse passen.")
            
            if len(signal) <= 2 * fenster:
                return None
            
            glatt = gaussian_filter1d(signal, max(1, glaettung_ms / 1000 / dt / 2.355))
            gradient = np.gradient(glatt, zeit)

            # Robuste Rauschschätzung am Aufnahmebeginn, vor dem Druckstoß.

            basis = gradient[:fenster]
            rauschen = 1.4826 * np.median(np.abs(basis - np.median(basis)))
            schwelle = max(6 * float(rauschen), 1e-9)
            kandidaten, _ = find_peaks(gradient, height=schwelle, prominence=schwelle)

            for index in kandidaten:
                if index < fenster or index + fenster >= len(signal):
                    continue

                anstieg = float(np.median(glatt[index:index + fenster])
                                - np.median(glatt[index - fenster:index]))
                
                if anstieg >= min_druckanstieg:
                    return float(zeit[index]), float(gradient[index]), anstieg
                
            return None

        for analyse, suffix in ((self, "p1"), (zweiter_sensor, "p4")):
            gipfel = erster_gradient(analyse)

            if gipfel is not None:
                r[f"t_{suffix}"], r[f"gradient_{suffix}"], r[f"druckanstieg_{suffix}"] = gipfel

        if r["t_p1"] is None or r["t_p4"] is None:
            return r
        
        differenz = r["t_p4"] - r["t_p1"]
        if differenz <= 2 * dt:
            r["grund"] = "Zeitfolge p1 vor p4 nicht ausreichend aufgelöst."
            return r
        
        r.update(schallgeschwindigkeit=float(sensorabstand / differenz), laufzeit=differenz,
                 grund="Erste positive Gradientengipfel: Laufzeitschätzung p1 → p4.")
        
        return r

    #Periodenmethode
    def schallgeschwindigkeit_periode(self, rohrlaenge=100.0, referenzzeit=None):
        """Separate Schätzung c=4L/T für das einfache Behälter-Rohr-Ventil-Modell.
    
        L ist der gesamte Wellenweg, unabhängig von der Position des Sensors.
        Fenster beginnen frühestens 1,5 s nach dem stärksten p1-Anstieg. Die
        Filterung entfernt nur lineare/quadratische Trends; kein Sollfrequenzband.
        Qualitätsgrenzen sind Heuristiken, kein Nachweis des physikalischen Modells.
        """
        zeit = np.asarray(self.time, dtype=float)
        signal = np.asarray(self.signal, dtype=float)

        if not np.isfinite(rohrlaenge) or rohrlaenge <= 0:
            raise ValueError("Gesamte Rohrlänge muss positiv und endlich sein.")
        
        if zeit.ndim != 1 or zeit.shape != signal.shape or len(zeit) < 100:
            raise ValueError("Mindestens 100 gleich lange Zeit- und Messwerte erforderlich.")
        
        if not np.all(np.isfinite(zeit)) or not np.all(np.isfinite(signal)):
            raise ValueError("Zeit und Signal müssen endlich sein.")
        
        dt = float(np.median(np.diff(zeit)))

        if dt <= 0 or not np.allclose(np.diff(zeit), dt, rtol=.01, atol=dt * 1e-6):
            raise ValueError("Die Zeitachse muss gleichmäßig sein und streng ansteigen.")
        
        if referenzzeit is None:
            glatt = gaussian_filter1d(signal, max(1, .005 / dt / 2.355))
            referenzzeit = float(zeit[np.argmax(np.gradient(glatt, zeit))])

        if not np.isfinite(referenzzeit) or not zeit[0] <= referenzzeit <= zeit[-1]:
            raise ValueError("Referenzzeit muss innerhalb der Aufnahme liegen.")
        
        ergebnis = dict(schallgeschwindigkeit=None, periode=None, periode_min=None,
                        periode_max=None, rohrlaenge=float(rohrlaenge),
                        referenzzeit=float(referenzzeit), fenster_geprueft=0,
                        fenster_bestaetigt=0, fenster=[], markierungen=None,
                        grund="Zu wenige vollständige Folgeschwingungen.")
        
        # Verhindert eine Geschwindigkeitsanzeige für kleine regelmäßige Störsignale.
        if np.ptp(signal) < .05:
            ergebnis["grund"] = "Druckänderung kleiner als 0,05 bar."
            return ergebnis
        
        zeilen = []

        #Tatsächlich geprüfte Extrema für eine nachvollziehbare Darstellung.
        darstellungen = []

        for versatz in (1.5, 2.5, 3.5):
            start = referenzzeit + versatz
            verfuegbar = zeit[-1] - start

            if verfuegbar < 3:
                continue

            dauern = sorted(set([d for d in (5.0, 7.0, 10.0) if d <= verfuegbar]
                                + [min(10.0, verfuegbar)]))
            
            for dauer in dauern:
                maske = (zeit >= start) & (zeit <= start + dauer)

                for grad in (1, 2):
                    r, (t, z, acf, _) = periodenfenster(zeit[maske], signal[maske], grad)

                    zeile = dict(start=float(start), ende=float(start + dauer),
                                 trendgrad=grad, bestaetigt=False, **r)
                    
                    zeilen.append(zeile)

                    if r["T_acf_s"] is None or r["ACF"] < .25:
                        continue

                    glatt = gaussian_filter1d(z, max(1, .02 / np.median(np.diff(t)) / 2.355))
                    
                    # Maxima und Minima getrennt prüfen
                    perioden = []
                    punkte = {}

                    for vorzeichen in (1, -1):
                        peaks, _ = find_peaks(vorzeichen * glatt, prominence=.1 * np.ptp(glatt),
                                               distance=max(1, round(.1 / np.median(np.diff(t)))))
                        
                        abstaende = np.diff(t[peaks])

                        if len(abstaende) < 2:
                            break

                        mittel = float(np.median(abstaende))

                        if np.ptp(abstaende) / mittel > .15 or abs(mittel / r["T_acf_s"] - 1) > .1:
                            break

                        perioden.append(mittel)
                        typ = "maxima" if vorzeichen == 1 else "minima"
                        absolute_zeiten = zeit[maske][0] + t[peaks]
                        punkte[typ] = [dict(zeit=float(tp), druck=float(np.interp(tp, zeit, signal)))
                                       for tp in absolute_zeiten]
                        
                    if len(perioden) == 2:
                        zeile.update(bestaetigt=True, T_maxima=perioden[0], T_minima=perioden[1])

                        darstellungen.append(dict(start=float(zeit[maske][0]),
                                                   ende=float(zeit[maske][-1]),
                                                   periode=r["T_acf_s"], trendgrad=grad, **punkte))
                        
        ergebnis.update(fenster=zeilen, fenster_geprueft=len(zeilen))

        bestaetigt = [r for r in zeilen if r["bestaetigt"]]

        ergebnis["fenster_bestaetigt"] = len(bestaetigt)

        starts = {r["start"] for r in bestaetigt}

        if len(starts) < 2 or len(bestaetigt) < len(zeilen) / 2:
            ergebnis["grund"] = "Zu wenige Fenster mit übereinstimmender ACF sowie Maxima- und Minima-Abständen."
            return ergebnis
        
        # Nicht nur bestätigte Teilfenster auswählen: andere ACF-Kandidaten mitprüfen.
        alle_perioden = [r["T_acf_s"] for r in zeilen if r["T_acf_s"] is not None]

        periode = float(np.median([r["T_acf_s"] for r in bestaetigt]))

        if np.ptp(alle_perioden) / periode > .1:
            ergebnis["grund"] = "Periodendauer hängt zu stark von der Fensterauswahl ab."
            return ergebnis
        
        ergebnis.update(schallgeschwindigkeit=4 * rohrlaenge / periode,
                        periode=periode, periode_min=float(min(alle_perioden)),
                        periode_max=float(max(alle_perioden)),
                        grund="Folgeschwingungen über mehrere Fenster und beide Extrematypen bestätigt.")
        
        #Ein bestätigtes Fenster nahe der Gesamtperiode zeigen
        ergebnis["markierungen"] = min(
            darstellungen, key=lambda f: (abs(f["periode"] - periode),
                                         -(f["ende"] - f["start"]), f["trendgrad"]))
        return ergebnis


    def perioden_referenzzeit(self):
        """Stärkster geglätteter Anstieg als gemeinsame Fensterreferenz."""

        glatt = gaussian_filter1d(np.asarray(self.signal, dtype=float),
                                  max(1, .005 / self.dt / 2.355))
        
        return float(self.time[np.argmax(np.gradient(glatt, self.time))])


 
    # NEU: Ganze Druckabfallphasen statt fester 50-/80-ms-Vergleiche bewerten.
    def schallgeschwindigkeit(
            self, rohrlaenge=100.0, min_druckstoss_amplitude=0.2,
            #amplituden_faktor=0.2 (Abfall im kurzen Vergleichsfenster)
            amplituden_faktor=0.3, glaettung_ms=3.0, vergleich_ms=50.0,
            phasen_glaettung_ms=10.0, min_phasenumkehr=0.01):
        """Reflexionskandidat aus der ersten ausreichend großen Abfallphase.

        Die Phase reicht vom lokalen Maximum zum nächsten deutlichen Minimum.
        Kleine Schwankungen unter min_phasenumkehr (bar) werden ignoriert.
        Eine ganze Phase muss standardmäßig mindestens 30 % der Stoßamplitude
        abbauen. Dies ist eine einstellbare Heuristik, kein Reflexionsnachweis.
        Der Zeitpunkt ist der stärkste negative Gradient innerhalb dieser Phase.
        vergleich_ms bleibt für alte Aufrufe erhalten, wird aber nicht verwendet.
        Die Zuordnung als physikalische Reflexion bleibt eine Annahme.
        """
        signal = np.asarray(self.signal, dtype=float)
        zeit = np.asarray(self.time, dtype=float)

        if signal.ndim != 1 or zeit.ndim != 1 or signal.shape != zeit.shape:
            raise ValueError("Zeit und Signal müssen gleich lange eindimensionale Arrays sein.")
        
        if len(signal) < 100 or not np.all(np.isfinite(signal)):
            return None
        
        if not np.all(np.isfinite(zeit)) or not np.all(np.diff(zeit) > 0):
            raise ValueError("Zeitachse muss endlich sein und streng ansteigen.")
        
        if not np.isfinite(rohrlaenge) or rohrlaenge <= 0 or not 0 < amplituden_faktor < 1:
            raise ValueError("Rohrlänge muss positiv sein und Amplitudenfaktor zwischen 0 und 1 liegen.")
        
        for wert in (min_druckstoss_amplitude, glaettung_ms,
                     phasen_glaettung_ms, min_phasenumkehr):
            
            if not np.isfinite(wert) or wert <= 0:
                raise ValueError("Amplituden- und Glättungsparameter müssen positiv und endlich sein.")
            
        dt = float(np.median(np.diff(zeit)))

        if not np.allclose(np.diff(zeit), dt, rtol=0.01, atol=dt * 1e-6):
            raise ValueError("Für die Glättung ist eine gleichmäßige Zeitachse erforderlich.")
        
        glatt = gaussian_filter1d(signal, max(1.0, glaettung_ms / 1000 / dt / 2.355))

        gradient = np.gradient(glatt, zeit)

        index_start = int(np.argmax(gradient))

        vor_samples = max(5, round(0.02 / dt))

        if index_start < vor_samples:
            return None
        
        startdruck = float(np.median(glatt[index_start-vor_samples:index_start]))

        # Die stärkere Glättung bestimmt nur Phasengrenzen, nicht den Messzeitpunkt.
        phasensignal = gaussian_filter1d(
            signal, max(1.0, phasen_glaettung_ms / 1000 / dt / 2.355))
        
        # Rauschen aus dem Glättungsrest schätzen, nicht aus dem ansteigenden
        # Druckniveau: Sonst würde ein langsamer Ventilschluss als Rauschen zählen.
        vorher = (signal - glatt)[index_start-vor_samples:index_start]
        rauschen = 1.4826 * np.median(np.abs(vorher - np.median(vorher)))
        umkehr = max(min_phasenumkehr, 6.0 * float(rauschen))
        maxima, _ = find_peaks(phasensignal, prominence=umkehr)
        minima, _ = find_peaks(-phasensignal, prominence=umkehr)
        kandidaten = []

        for index_max in maxima[maxima > index_start]:
            position = int(np.searchsorted(minima, index_max, side="right"))

            if position == len(minima):
                continue  # Unvollständiger Abfall am Aufnahmeende ist kein Kandidat.

            index_min = int(minima[position])
            amplitude = float(phasensignal[index_max] - startdruck)

            if amplitude < min_druckstoss_amplitude:
                continue

            abfall = float(phasensignal[index_max] - phasensignal[index_min])
            mindest_abfall = max(0.03, amplituden_faktor * amplitude)

            if abfall < mindest_abfall:
                continue

            index_reflexion = int(index_max + np.argmin(gradient[index_max:index_min + 1]))

            if gradient[index_reflexion] >= 0:
                continue

            kandidaten.append({
                "t_maximum": float(zeit[index_max]),
                "t_minimum": float(zeit[index_min]),
                "t_reflexion": float(zeit[index_reflexion]),
                "druck_maximum": float(phasensignal[index_max]),
                "druck_minimum": float(phasensignal[index_min]),
                "druckstoss_amplitude": amplitude,
                "reflexions_amplitude": abfall,
                "mindest_amplitude": mindest_abfall,
                "gradient_reflexion": float(gradient[index_reflexion]),
            })

        if not kandidaten:
            return None
        
        # Chronologische Auswahl; spätere Punkte werden nicht künstlich bevorzugt.
        gewaehlt = kandidaten[0]
        laufzeit = gewaehlt["t_reflexion"] - float(zeit[index_start])

        return {
            **gewaehlt,
            "schallgeschwindigkeit": 2.0 * rohrlaenge / laufzeit,
            "laufzeit": laufzeit, "t_start": float(zeit[index_start]),
            "startdruck": startdruck, "phasen_umkehrschwelle": umkehr,
            "methode": "Gesamter Druckabfall einer Phase; stärkster negativer Gradient",
            "status": "Reflexionskandidat", "anzahl_kandidaten": len(kandidaten),
            "kandidaten": kandidaten,
        }

    
