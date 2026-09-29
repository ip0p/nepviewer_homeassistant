# Nepviewer Solar für Home Assistant

Diese Integration verbindet deinen Home Assistant mit deiner NEP Solarüberwachung.

## Features
- Aktuelle Solarleistung (Watt)
- Heute erzeugte Energie (kWh)
- Gesamterzeugung (kWh)
- Status der Anlage
- Mehrere Anlagen pro NEPViewer-Konto
- Automatische Erneuerung abgelaufener API-Tokens

## Installation
1. Über HACS als benutzerdefiniertes Repository hinzufügen.
2. Integration "Nepviewer Solar" installieren.
3. Integration über **Einstellungen → Geräte & Dienste → Integration hinzufügen**
   einrichten.
4. Mit derselben E-Mail-Adresse und demselben Passwort wie in der
   NEPViewer-App anmelden.

## Hinweise
- Die Integration meldet sich bei Bedarf automatisch neu an, wenn der
  kurzlebige NEPViewer-Token abläuft.
- Getestet mit der v2-API von nepviewer.net und Home Assistant 2026.9.4.
- Bestehende Konfigurationen mit einem alten Token zeigen nach dessen Ablauf
  einen Reparaturdialog zur einmaligen Anmeldung an.

## Entwicklung

Die API-Tests können mit `pytest -q tests/test_nepviewer_api.py` ausgeführt
werden. Sie prüfen die aktuelle Request-Signatur, Anmeldung und automatische
Token-Erneuerung.

## Lizenz
MIT License

---

Projekt basiert auf liebevoller Arbeit von Basti und Copilot ❤️
