# 🐛 Debug-Anleitung für bedingte Felder

## Problem: Felder werden nicht angezeigt

Wenn Felder mit `showIf` Bedingungen nicht angezeigt werden, folgen Sie dieser Schritt-für-Schritt Anleitung:

### Schritt 1: Debug-Modus aktivieren

1. Starten Sie die Streamlit-App
2. In der **Sidebar** finden Sie eine Checkbox "🐛 Debug Modus"
3. Aktivieren Sie diese Checkbox

### Schritt 2: Form ausfüllen und beobachten

1. Navigieren Sie zur Section "Angaben zur einzustellenden/betreffenden Person"
2. Bei "Antrag auf" wählen Sie **"Einstellung"**
3. Im Debug-Bereich sehen Sie:
   - Alle aktuellen Form-Daten
   - Welche Bedingungen geprüft werden
   - Warum Felder angezeigt oder versteckt werden

### Schritt 3: Häufige Probleme

#### Problem: Feld erscheint nicht trotz korrekter Auswahl

**Mögliche Ursache 1: Falscher Feldname in `showIf`**
```json
// ❌ Falsch
"showIf": { "field": "antrag_typ", "op": "=", "value": "einstellung" }

// ✅ Richtig
"showIf": { "field": "antrag.typ", "op": "=", "value": "einstellung" }
```

**Mögliche Ursache 2: Falscher Value**
```json
// Prüfen Sie, dass der value exakt mit dem option value übereinstimmt
"options": [
  { "value": "einstellung", "label": "Einstellung" }
]

"showIf": { "field": "antrag.typ", "op": "=", "value": "einstellung" }
```

**Mögliche Ursache 3: Feld wurde noch nicht ausgefüllt**
- Das abhängige Feld wird erst angezeigt, NACHDEM das Quellfeld ausgefüllt wurde
- Werte müssen gespeichert sein (durch Klick auf "Weiter" oder direktes Ausfüllen)

#### Problem: Verschachtelte Bedingungen (allOf/anyOf) funktionieren nicht

**Beispiel aus Ihrer data.json:**
```json
{
  "showIf": {
    "allOf": [
      { "field": "antrag.typ", "op": "=", "value": "einstellung" },
      { "field": "person.neueinstellung.fruehereBeschaeftigung.vorhanden", "op": "=", "value": "ja" }
    ]
  }
}
```

**Debug-Schritte:**
1. Aktivieren Sie Debug-Modus
2. Scrollen Sie zum bedingten Feld
3. Klicken Sie auf den Debug-Expander für dieses Feld
4. Prüfen Sie jede einzelne Bedingung:
   - ✅ Ist `antrag.typ` = `"einstellung"`?
   - ✅ Ist `person.neueinstellung.fruehereBeschaeftigung.vorhanden` = `"ja"`?
   - ✅ Beide müssen TRUE sein für `allOf`

### Schritt 4: Test-Skript ausführen

Sie können die Bedingungslogik auch offline testen:

```powershell
python test_conditions.py
```

Dies testet alle Bedingungen ohne die UI zu starten.

## Spezifisches Problem: Neueinstellungs-Felder

### Feld 1: "Bei Neueinstellung: Bestanden bereits Beschäftigungsverhältnisse..."

**Bedingung:**
```json
"showIf": { "field": "antrag.typ", "op": "=", "value": "einstellung" }
```

**Damit es erscheint:**
1. Gehen Sie zur Section "Antrag auf"
2. Wählen Sie "Einstellung" aus dem Dropdown
3. Gehen Sie zur Section "Angaben zur einzustellenden/betreffenden Person"
4. ✅ Das Feld sollte jetzt erscheinen

### Feld 2: "Angaben zu früheren Beschäftigungen" (Group)

**Bedingung:**
```json
"showIf": {
  "allOf": [
    { "field": "antrag.typ", "op": "=", "value": "einstellung" },
    { "field": "person.neueinstellung.fruehereBeschaeftigung.vorhanden", "op": "=", "value": "ja" }
  ]
}
```

**Damit es erscheint:**
1. ✅ "Antrag auf" muss auf "Einstellung" gesetzt sein
2. ✅ "Bestanden bereits Beschäftigungsverhältnisse..." muss auf "ja" gesetzt sein
3. Beide Bedingungen müssen erfüllt sein!

## Debug-Output verstehen

Im Debug-Modus sehen Sie:

```
🔍 Debug: person.neueinstellung.fruehereBeschaeftigung.vorhanden
Feld ID: person.neueinstellung.fruehereBeschaeftigung.vorhanden
Label: Bei Neueinstellung: Bestanden bereits...
ShowIf Bedingung:
{
  "field": "antrag.typ",
  "op": "=",
  "value": "einstellung"
}

🔍 Prüfe: antrag.typ (Wert: einstellung) = einstellung
   ➡️ Ergebnis: True
```

- **True** = Feld wird angezeigt ✅
- **False** = Feld wird versteckt ❌

## Lösungen für typische Probleme

### Problem: "antrag.typ" ist leer/None

**Lösung:**
1. Gehen Sie zur Section "Antrag auf"
2. Wählen Sie eine Option aus
3. Die Option wird automatisch gespeichert
4. Navigieren Sie zurück zur Person-Section

### Problem: Felder bleiben versteckt nach Auswahl

**Lösung:**
```python
# Das ist ein Streamlit-Rerun Problem
# Lösung ist bereits implementiert:
# - Bei jeder Änderung eines single_select wird der Wert sofort gespeichert
# - Streamlit aktualisiert die Seite automatisch
```

Falls das Problem weiterhin besteht:
1. Klicken Sie auf "Weiter" und dann "Zurück"
2. Oder: Nutzen Sie die Sidebar-Navigation um die Section neu zu laden

### Problem: Group-Felder werden nicht gerendert

**Im Code überprüfen:**
```python
# In render_field() Methode:
elif field_type == 'group':
    if self.should_show_field(field):  # ✅ Doppelte Prüfung!
        st.markdown(f"**{label}**")
        with st.container():
            for subfield in field.get('fields', []):
                self.render_field(subfield, section_id)
```

**Hinweis:** Die Bedingung wird bereits am Anfang von `render_field()` geprüft!

## Erweiterte Debugging-Optionen

### 1. Alle Form-Daten anzeigen

Im Debug-Modus unter "Debug Info" sehen Sie alle gespeicherten Werte:
```json
{
  "antrag.typ": "einstellung",
  "person.nachname": "Müller",
  "person.vorname": "Hans",
  ...
}
```

### 2. Browser-Console nutzen

Öffnen Sie die Browser-Console (F12) und suchen Sie nach Streamlit-Fehlern.

### 3. Python-Console Logging

Fügen Sie temporär Debug-Prints ein:
```python
def should_show_field(self, field: Dict[str, Any]) -> bool:
    if 'showIf' not in field:
        return True
    result = self.evaluate_condition(field['showIf'])
    print(f"DEBUG: {field['id']} -> {result}")  # Temporär!
    return result
```

## Kontakt & Support

Bei weiteren Problemen:
1. Aktivieren Sie den Debug-Modus
2. Machen Sie einen Screenshot der Debug-Info
3. Notieren Sie die genauen Schritte zum Reproduzieren
