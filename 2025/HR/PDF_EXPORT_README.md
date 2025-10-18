# PDF-Export Funktionalität - THWS Antragsformular

## 📋 Übersicht

Das Streamlit-Formular kann nun am Ende als **professionell formatiertes PDF** exportiert werden. Die Implementierung verwendet:
- **Jinja2** für HTML-Template-Rendering
- **WeasyPrint** für HTML-zu-PDF-Konvertierung
- Automatische Datenstruktur-Transformation

## 🎯 Implementierte Komponenten

### 1. **template.html** - Jinja2 HTML-Template
- Vollständiges HTML-Template mit CSS für PDF-Formatierung
- A4-Seitenlayout mit korrekten Rändern (18mm/16mm/20mm/16mm)
- Professionelle Tabellen und Grid-Layouts
- Checkboxen für Auswahlfelder
- Seitenumbrüche für mehrseitige Dokumente
- Bedingte Anzeige von Sections basierend auf Formulardaten

### 2. **pdf_generator.py** - PDF-Generator-Modul
Enthält die `PDFGenerator` Klasse mit folgenden Methoden:

#### `__init__(template_path)`
- Initialisiert Jinja2-Environment
- Lädt HTML-Template

#### `prepare_data(form_data)`
- **Kritische Funktion**: Konvertiert flache Streamlit-Daten in verschachtelte Struktur
- Mapping-Logik für alle Sections:
  - `absender.*` → `absender`
  - `person.*` → `person` (mit Unterstrukturen)
  - `vertrag.*` → `vertrag` (mit Befristungsdetails)
  - `arbeit.*` → `arbeit`
  - `finanzierung.zeilen[n].*` → Array-Handling
  - etc.

#### `generate_html(form_data)`
- Rendert Jinja2-Template mit Daten
- Returns: HTML-String

#### `generate_pdf(form_data, output_path=None)`
- Generiert PDF mit WeasyPrint
- Optional: Speichert PDF in Datei
- Returns: PDF als Bytes

#### `get_filename(form_data)`
- Generiert intelligenten Dateinamen
- Format: `THWS_Antrag_{typ}_{nachname}_{vorname}_{timestamp}.pdf`

### 3. **app.py** - Streamlit Integration

#### Import hinzugefügt:
```python
from pdf_generator import PDFGenerator
```

#### `render_summary()` erweitert:
- Neue 4. Spalte mit PDF-Download-Button
- Try-Catch für robuste Fehlerbehandlung
- Automatische PDF-Generierung on-the-fly

```python
with col3:
    try:
        pdf_gen = PDFGenerator(template_path="template.html")
        pdf_bytes = pdf_gen.generate_pdf(st.session_state.form_data)
        filename = pdf_gen.get_filename(st.session_state.form_data)
        
        st.download_button(
            label="📄 PDF herunterladen",
            data=pdf_bytes,
            file_name=filename,
            mime="application/pdf"
        )
    except Exception as e:
        st.error(f"PDF-Generierung fehlgeschlagen: {str(e)}")
```

## 📦 Installation

### Benötigte Pakete (bereits in requirements.txt):
```bash
pip install jinja2>=3.1.2
pip install weasyprint>=60.0
```

### WeasyPrint Dependencies (Windows):
WeasyPrint benötigt zusätzliche System-Bibliotheken:
- **GTK3**: Download von https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer
- Oder verwende conda: `conda install -c conda-forge weasyprint`

## 🚀 Verwendung

### Für Benutzer:
1. Formular vollständig ausfüllen
2. Zur Zusammenfassungsseite navigieren
3. Button **"📄 PDF herunterladen"** klicken
4. PDF wird automatisch generiert und heruntergeladen

### Für Entwickler:

#### Manueller PDF-Export (außerhalb Streamlit):
```python
from pdf_generator import PDFGenerator

# Lade Formulardaten
form_data = {
    'absender.name': 'Max Mustermann',
    'person.nachname': 'Müller',
    # ... weitere Felder
}

# Generiere PDF
generator = PDFGenerator('template.html')
pdf_bytes = generator.generate_pdf(form_data)

# Speichere in Datei
with open('output.pdf', 'wb') as f:
    f.write(pdf_bytes)
```

## 🎨 Template-Anpassungen

### Jinja2-Syntax im Template:

#### Makros:
```jinja2
{% macro cb(cond) -%}
    <span class="check {{ 'checked' if cond else '' }}">
        {{ '■' if cond else ' ' }}
    </span>
{%- endmacro %}

{% macro opt(val, expected, label) -%}
    {{ cb(val == expected) }} {{ label }}
{%- endmacro %}
```

#### Bedingte Anzeige:
```jinja2
{% if vertrag.ende.art == 'befristet' %}
    <tr><td>Befristungsdetails...</td></tr>
{% endif %}
```

#### Schleifen (Finanzierungszeilen):
```jinja2
{% for z in finanzierung.zeilen %}
    <tr>
        <td>{{ z.fin.anteil_prozent }}</td>
        <td>{{ z.fin.kapitel }}</td>
        <!-- ... -->
    </tr>
{% endfor %}
```

## 🐛 Fehlerbehandlung

### Mögliche Fehler:

1. **WeasyPrint nicht installiert**
   - Fehlermeldung: "Import 'weasyprint' could not be resolved"
   - Lösung: `pip install weasyprint`

2. **GTK3-Bibliotheken fehlen (Windows)**
   - Fehlermeldung: "OSError: cannot load library 'gobject-2.0-0'"
   - Lösung: GTK3 Runtime installieren

3. **Template nicht gefunden**
   - Fehlermeldung: "TemplateNotFound: template.html"
   - Lösung: Stelle sicher dass template.html im Working Directory liegt

4. **Datenstruktur-Fehler**
   - Fehlermeldung: "KeyError: ..."
   - Lösung: Überprüfe `prepare_data()` Mapping-Logik

## 📊 Datenstruktur-Mapping

### Flache Struktur (Streamlit Session State):
```python
{
    'absender.name': 'Max Mustermann',
    'absender.orgeinheit': 'Fakultät Informatik',
    'person.nachname': 'Müller',
    'person.vorname': 'Anna',
    'finanzierung.zeilen[0].fin.anteil_prozent': 100,
    'finanzierung.zeilen[0].fin.kapitel': '1234'
}
```

### Verschachtelte Struktur (Template):
```python
{
    'absender': {
        'name': 'Max Mustermann',
        'orgeinheit': 'Fakultät Informatik'
    },
    'person': {
        'nachname': 'Müller',
        'vorname': 'Anna'
    },
    'finanzierung': {
        'zeilen': [
            {
                'fin': {
                    'anteil_prozent': 100,
                    'kapitel': '1234'
                }
            }
        ]
    }
}
```

## ✅ Vorteile dieser Implementierung

1. **Saubere Trennung**: Template, Generator, UI sind getrennt
2. **Wiederverwendbar**: `PDFGenerator` kann auch außerhalb Streamlit genutzt werden
3. **Professionelles Layout**: A4-Format, korrekte Ränder, Seitenumbrüche
4. **Fehlerbehandlung**: Try-Catch verhindert App-Crashes
5. **Intelligente Dateinamen**: Automatisch generiert aus Formulardaten
6. **On-the-fly**: PDF wird bei Bedarf generiert, keine Zwischenspeicherung

## 🔧 Erweitungsmöglichkeiten

### Zukünftige Verbesserungen:
1. **PDF-Vorschau** vor Download
2. **Wasserzeichen** für Entwürfe
3. **Digitale Signatur**-Unterstützung
4. **Email-Versand** direkt aus der App
5. **PDF/A-Konformität** für Langzeitarchivierung
6. **Template-Auswahl** (verschiedene Designs)

## 📝 Beispiel-Workflow

```
Benutzer füllt Formular aus
    ↓
Klickt "Abschließen"
    ↓
Zusammenfassungsseite wird angezeigt
    ↓
Klickt "📄 PDF herunterladen"
    ↓
1. PDFGenerator lädt template.html
2. prepare_data() transformiert Session State
3. Jinja2 rendert HTML mit Daten
4. WeasyPrint konvertiert HTML → PDF
5. Browser startet Download
```

## 🎯 Testing

### Testfälle:
1. ✅ Vollständiges Formular → PDF generieren
2. ✅ Teilweise ausgefülltes Formular → Leere Felder in PDF
3. ✅ Repeating Groups (Finanzierung) → Tabelle mit mehreren Zeilen
4. ✅ Bedingte Felder → Nur sichtbare Felder im PDF
5. ✅ Lange Texte → Automatischer Zeilenumbruch
6. ✅ Sonderzeichen (ä,ö,ü,ß) → Korrekte UTF-8-Kodierung

## 📞 Support

Bei Problemen:
1. Überprüfe Installation: `pip list | grep -E "(jinja2|weasyprint)"`
2. Teste Template manuell: `python pdf_generator.py`
3. Aktiviere Debug-Modus in Streamlit
4. Prüfe Logs für detaillierte Fehlermeldungen
