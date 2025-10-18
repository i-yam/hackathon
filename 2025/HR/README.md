# THWS Antragsformular - Streamlit Flow UI

Eine benutzerfreundliche Streamlit-Anwendung zur Darstellung und Bearbeitung des THWS-Antragsformulars als interaktiver Flow.

## 🚀 Features

- **Schrittweise Navigation**: Durchlaufen Sie das Formular Section für Section
- **Intelligente Validierung**: Automatische Überprüfung erforderlicher Felder
- **Bedingte Felder**: Felder werden dynamisch basierend auf vorherigen Eingaben angezeigt
- **Fortschrittsanzeige**: Visualisierung des Formularfortschritts
- **Sidebar-Navigation**: Schneller Zugriff auf alle Sections
- **Daten-Export**: Speichern Sie Ihre Eingaben als JSON
- **Zusammenfassung**: Übersicht aller eingegebenen Daten am Ende
- **🤖 Chat-Assistent**: KI-gestützter Assistent mit Ollama (mistral-small3.2)
  - Kontextbewusste Hilfe beim Ausfüllen
  - Erklärung von Formularfeldern
  - Echtzeit-Streaming-Antworten
  - Lokale KI ohne Cloud-Abhängigkeit

## 📋 Unterstützte Feldtypen

- ✅ Text Input
- ✅ Textarea
- ✅ Email
- ✅ Date
- ✅ Single Select (Dropdown)
- ✅ Multi Select
- ✅ Number Input
- ✅ Boolean (Checkbox)
- ✅ Date Range
- ✅ Repeating Groups (dynamische Listen)
- ✅ Conditional Groups (verschachtelte Felder mit Bedingungen)

## 🛠️ Installation

### Voraussetzungen
- Python 3.8 oder höher
- pip

### Schritte

1. **Abhängigkeiten installieren**:
   ```powershell
   pip install -r requirements.txt
   ```

2. **Anwendung starten**:
   ```powershell
   streamlit run app.py
   ```

3. **Browser öffnen**:
   Die App wird automatisch im Browser geöffnet (normalerweise auf `http://localhost:8501`)

## 📖 Verwendung

### Navigation

1. **Sections durchlaufen**: 
   - Verwenden Sie die Buttons "Weiter ➡️" und "⬅️ Zurück" am unteren Rand
   - Oder nutzen Sie die Sidebar-Navigation für direkten Zugriff

2. **Felder ausfüllen**:
   - Erforderliche Felder sind mit einem 🔴 markiert
   - Bedingte Felder erscheinen automatisch basierend auf Ihren Eingaben

3. **Validierung**:
   - Die App prüft automatisch, ob alle erforderlichen Felder ausgefüllt sind
   - Fehlermeldungen werden angezeigt, wenn Felder fehlen

4. **Zusammenfassung**:
   - Nach Abschluss aller Sections sehen Sie eine Übersicht
   - Exportieren Sie Ihre Daten als JSON

### 🤖 Chat-Assistent verwenden

Der integrierte KI-Assistent hilft Ihnen beim Ausfüllen:

1. **Chat öffnen**: Klicken Sie in der Sidebar auf "🤖 💬 Chat-Assistent"
2. **Frage stellen**: Geben Sie Ihre Frage im Chat-Feld ein
3. **Antwort erhalten**: Der Assistent antwortet in Echtzeit mit Streaming

**Beispiel-Fragen:**
- "Was bedeutet das Feld 'Befristungsgrundlage'?"
- "Welche Unterlagen muss ich beifügen?"
- "Wie fülle ich die Finanzierungsangaben aus?"

**Voraussetzungen:**
- Ollama-Server muss unter `YOUR_OLLAMA_SERVER_ENDPOINT` erreichbar sein
- Modell `mistral-small3.2` muss installiert sein

**Mehr Details:** Siehe `CHAT_ASSISTANT.md`

### Daten speichern

- **Während der Bearbeitung**: Klicken Sie auf "💾 Formular als JSON speichern" in der Sidebar
- **Am Ende**: Nutzen Sie den "💾 JSON herunterladen" Button in der Zusammenfassung

## 🔧 Anpassung

### data.json Struktur

Die Anwendung liest die Formularstruktur aus `data.json`. Unterstützte Eigenschaften:

```json
{
  "meta": {
    "title": "Formulartitel",
    "version": "1.0",
    "locale": "de-DE"
  },
  "root": {
    "sections": [
      {
        "id": "section_id",
        "title": "Section Titel",
        "fields": [...]
      }
    ]
  }
}
```

### Feldtypen

Jedes Feld kann folgende Eigenschaften haben:

- `id`: Eindeutige ID
- `label`: Anzeigetext
- `type`: Feldtyp (siehe unterstützte Typen oben)
- `required`: Boolean, ob Feld erforderlich ist
- `help`: Hilfetext
- `showIf`: Bedingung für bedingte Anzeige
- `options`: Array von Optionen (für select-Felder)

### Bedingte Logik (showIf)

```json
{
  "showIf": {
    "field": "other_field_id",
    "op": "=",
    "value": "expected_value"
  }
}
```

Unterstützte Operatoren:
- `=`: Gleich
- `!=`: Ungleich
- `blank`: Feld ist leer
- `!blank`: Feld ist nicht leer

Kombinationen:
- `anyOf`: Mindestens eine Bedingung muss erfüllt sein
- `allOf`: Alle Bedingungen müssen erfüllt sein

## 🎨 Design

Die App verwendet ein modernes, benutzerfreundliches Design mit:
- THWS-Farbschema (Blautöne)
- Responsive Layout
- Intuitive Icons und Visualisierungen
- Klare Fehleranzeigen

## 🐛 Fehlerbehebung

### Debug-Modus verwenden

Die App verfügt über einen eingebauten Debug-Modus zum Troubleshooting:

1. **Debug-Modus aktivieren**: In der Sidebar → "🐛 Debug Modus" Checkbox aktivieren
2. **Form-Daten anzeigen**: Sehen Sie alle gespeicherten Werte in Echtzeit
3. **Bedingungen prüfen**: Bei bedingten Feldern (showIf) wird die Auswertung angezeigt
4. **Schritt-für-Schritt**: Jede Bedingung wird einzeln geprüft und das Ergebnis angezeigt

### Häufige Probleme bei bedingten Feldern

**Problem**: Felder mit `showIf` werden nicht angezeigt
- **Lösung**: Aktivieren Sie den Debug-Modus und prüfen Sie:
  - Ist das Quellfeld ausgefüllt?
  - Stimmt der Wert exakt überein?
  - Bei `allOf`: Sind ALLE Bedingungen erfüllt?
  - Bei `anyOf`: Ist MINDESTENS EINE Bedingung erfüllt?

**Beispiel**: "Neueinstellungs-Felder" erscheinen nicht
1. Debug-Modus aktivieren
2. Zu Section "Antrag auf" gehen
3. "Einstellung" auswählen
4. Zu Section "Person" gehen
5. Im Debug-Bereich prüfen: `"antrag.typ": "einstellung"`
6. Feld sollte jetzt erscheinen

**Weitere Hilfe**: 
- 📄 Siehe `DEBUG_GUIDE.md` für detaillierte Anleitung
- 📄 Siehe `FEHLERSUCHE.md` für Schritt-für-Schritt Troubleshooting
- 📄 Siehe `ZUSAMMENFASSUNG.txt` für Quick Reference

### Offline-Test der Bedingungslogik

```powershell
python test_conditions.py
```

Dies testet die Bedingungsauswertung ohne die UI zu starten.

## 🐛 Fehlerbehebung

**Problem**: App startet nicht
- Lösung: Stellen Sie sicher, dass alle Abhängigkeiten installiert sind: `pip install -r requirements.txt`

**Problem**: data.json wird nicht gefunden
- Lösung: Stellen Sie sicher, dass `data.json` im selben Verzeichnis wie `app.py` liegt

**Problem**: Felder werden nicht korrekt angezeigt
- Lösung: Überprüfen Sie die JSON-Struktur auf Syntaxfehler

## 📝 Lizenz

Dieses Projekt wurde für die THWS entwickelt.

## 🤝 Beitragen

Verbesserungsvorschläge und Bug-Reports sind willkommen!
