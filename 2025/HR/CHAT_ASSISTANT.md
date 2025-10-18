# 🤖 Chat-Assistent - Benutzeranleitung

## Übersicht

Der integrierte Chat-Assistent nutzt Ollama mit dem Modell "mistral-small3.2", um Ihnen beim Ausfüllen des THWS-Antragsformulars zu helfen.

## ✨ Features

- **Kontextbewusst**: Der Assistent kennt den aktuellen Stand Ihres Formulars
- **Echtzeit-Hilfe**: Sofortige Antworten auf Ihre Fragen
- **Streaming**: Antworten werden während der Generierung angezeigt
- **Konversations-Historie**: Alle Nachrichten werden gespeichert
- **Formular-Expertise**: Speziell trainiert für das THWS-Formular

## 🚀 Chat-Assistent aktivieren

### Schritt 1: Öffnen Sie den Chat
1. Starten Sie die Streamlit-App: `streamlit run app.py`
2. In der **linken Sidebar** finden Sie den Button "🤖 💬 Chat-Assistent"
3. Klicken Sie darauf, um den Chat zu öffnen

### Schritt 2: Chat-Interface
Der Chat erscheint auf der **linken Seite** der App:
- **Links**: Chat-Assistent
- **Rechts**: Formular

## 💬 Chat verwenden

### Frage stellen
1. Geben Sie Ihre Frage im Textfeld "Ihre Frage:" ein
2. Klicken Sie auf "📤 Senden" oder drücken Sie Enter
3. Der Assistent antwortet in Echtzeit (Streaming)

### Beispiel-Fragen

**Allgemeine Hilfe:**
- "Was bedeutet das Feld 'Befristungsgrundlage'?"
- "Wie fülle ich die Finanzierungsangaben aus?"
- "Welche Unterlagen muss ich beifügen?"

**Formular-spezifisch:**
- "Ich habe 'Einstellung' gewählt, welche Felder muss ich ausfüllen?"
- "Was ist der Unterschied zwischen TzBfG und WissZeitVG?"
- "Wie funktionieren die bedingten Felder?"

**Technische Fragen:**
- "Warum wird ein Feld nicht angezeigt?"
- "Wie speichere ich meine Eingaben?"
- "Kann ich das Formular zwischenspeichern?"

## ⚙️ Verbindungseinstellungen

### Ollama-Server
- **Endpoint**: `YOUR_OLLAMA_SERVER_ENDPOINT`
- **Modell**: `mistral-small3.2`

### Verbindung testen
1. Öffnen Sie den Chat-Assistenten
2. Klicken Sie auf "ℹ️ Verbindungsinformationen"
3. Klicken Sie auf "🔄 Verbindung testen"

**Erwartetes Ergebnis:**
```
✅ Verbunden! Verfügbare Modelle: mistral-small3.2, ...
```

**Bei Fehlern:**
```
❌ Keine Verbindung zu YOUR_OLLAMA_SERVER_ENDPOINT möglich
```

### Fehlerbehebung

#### Problem: "Keine Verbindung möglich"
**Ursachen:**
- Ollama-Server ist nicht erreichbar
- Firewall blockiert den Zugriff
- Falsche IP-Adresse/Port

**Lösung:**
1. Prüfen Sie, ob der Ollama-Server läuft:
   ```bash
   curl YOUR_OLLAMA_SERVER_ENDPOINT/api/tags
   ```
2. Prüfen Sie die Netzwerkverbindung
3. Passen Sie die Server-URL in `app.py` an (Zeile 140):
   ```python
   st.session_state.ollama_chat = OllamaChat(
       base_url="YOUR_OLLAMA_SERVER_ENDPOINT",  # Ändern Sie dies
       model="mistral-small3.2"
   )
   ```

#### Problem: "Modell nicht gefunden"
**Ursache:** Das Modell "mistral-small3.2" ist nicht installiert

**Lösung:**
1. Auf dem Ollama-Server ausführen:
   ```bash
   ollama pull mistral-small3.2
   ```
2. Oder verwenden Sie ein anderes Modell:
   ```python
   model="llama2"  # Oder ein anderes verfügbares Modell
   ```

#### Problem: "Timeout"
**Ursache:** Der Server antwortet zu langsam

**Lösung:**
- Erhöhen Sie das Timeout in `ollama_chat.py` (Zeile 78):
  ```python
  timeout=120  # Statt 60 Sekunden
  ```

## 🔧 Erweiterte Funktionen

### Konversation zurücksetzen
- Klicken Sie auf "🗑️ Konversation zurücksetzen"
- Alle Chat-Nachrichten werden gelöscht
- Neue Konversation beginnt

### Chat schließen
- Klicken Sie erneut auf "🤖 💬 Chat-Assistent" in der Sidebar
- Der Chat wird ausgeblendet
- Das Formular nutzt die volle Breite

## 🎯 Was der Assistent kann

### ✅ Kann helfen mit:
- Erklärung von Formularfeldern
- Ausfüllhilfe und Tipps
- Rechtliche Begriffe erklären (TzBfG, WissZeitVG, etc.)
- Navigation durchs Formular
- Fehlersuche bei bedingten Feldern
- Allgemeine Fragen zum Einstellungsprozess

### ❌ Kann NICHT:
- Formular direkt ausfüllen
- Rechtliche Beratung geben
- Entscheidungen für Sie treffen
- Auf externe Systeme zugreifen

## 💡 Best Practices

### Effektive Fragen stellen
✅ **Gut:**
- "Was bedeutet 'Befristungsgrundlage § 14 Abs. 2 TzBfG'?"
- "Ich habe 'befristet' gewählt, welche Felder erscheinen jetzt?"

❌ **Weniger gut:**
- "Hilfe!"
- "Was soll ich tun?"

### Kontext nutzen
Der Assistent kennt Ihre aktuellen Formular-Daten:
- "Welche Unterlagen brauche ich für meine Auswahl?"
- "Ist meine Finanzierung vollständig?"

### Schrittweise vorgehen
- Stellen Sie eine Frage nach der anderen
- Lassen Sie den Assistenten antworten, bevor Sie weiterfragen

## 🔒 Datenschutz

- **Lokaler Server**: Alle Daten bleiben in Ihrem Netzwerk
- **Keine Cloud**: Keine Daten werden an externe Server gesendet
- **Session-basiert**: Chat-Historie wird nur während der Session gespeichert
- **Kein Logging**: Konversationen werden nicht dauerhaft gespeichert

## 📝 Offline-Test

Sie können den Ollama-Client auch unabhängig testen:

```bash
# Im Terminal
cd c:\Users\djebemo\THWS_Hackaton_2025
python ollama_chat.py
```

**Ausgabe:**
```
============================================================
OLLAMA CONNECTION TEST
============================================================

✅ Verbunden! Verfügbare Modelle: mistral-small3.2

Teste Chat-Funktion...
------------------------------------------------------------
Antwort: Hallo! Ich bin ein KI-Assistent...
------------------------------------------------------------
```

## 🛠️ Technische Details

### Architektur
```
Streamlit UI ──> OllamaChat ──> HTTP REST API ──> Ollama Server
                                                   └─> mistral-small3.2
```

### API-Endpoints
- **Tags**: `GET /api/tags` - Liste verfügbarer Modelle
- **Chat**: `POST /api/chat` - Chat-Interaktion (streaming)

### Dateien
- `app.py` - Hauptanwendung mit Chat-Integration
- `ollama_chat.py` - Ollama-Client-Bibliothek
- `requirements.txt` - Dependencies (inkl. `requests`)

## 🎨 UI-Anpassungen

### Chat-Position ändern
In `app.py`, Zeile 743:
```python
col_chat, col_form = st.columns([1, 2])  # 1:2 Verhältnis
# Ändern Sie zu [1, 3] für schmaleren Chat
# Oder [2, 3] für breiteren Chat
```

### Chat-Farben anpassen
In `app.py`, CSS-Bereich (Zeile 75-120):
```css
.chat-message-user {
    background-color: #0066cc;  /* Ändern Sie die Farbe */
}
.chat-message-assistant {
    background-color: #f0f2f6;  /* Ändern Sie die Farbe */
}
```

## 📚 Weitere Ressourcen

- [Ollama Dokumentation](https://github.com/ollama/ollama)
- [Mistral AI Modelle](https://mistral.ai/)
- [Streamlit Chat Docs](https://docs.streamlit.io/library/api-reference/chat)

## 🆘 Support

Bei Problemen:
1. Aktivieren Sie den Debug-Modus
2. Testen Sie die Ollama-Verbindung
3. Prüfen Sie die Browser-Console (F12)
4. Führen Sie `python ollama_chat.py` aus

---

**Version**: 1.0  
**Letzte Aktualisierung**: Oktober 2025  
**Kompatibel mit**: Streamlit 1.31.0, Ollama API v1
