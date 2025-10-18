# 🔍 Schritt-für-Schritt Fehlersuche: Neueinstellungs-Felder

## Status: ✅ Debug-Modus wurde hinzugefügt!

Die App wurde mit einem Debug-Modus erweitert, um das Problem zu identifizieren.

## So finden Sie den Fehler:

### 1️⃣ **App neu starten mit Debug-Modus**

```powershell
streamlit run app.py
```

### 2️⃣ **Debug-Modus aktivieren**

- In der **linken Sidebar** finden Sie: "🐛 Debug Modus"
- ✅ Aktivieren Sie die Checkbox

### 3️⃣ **Zum Formular navigieren**

1. **Section 1:** Geben Sie Absender-Daten ein
2. **Section 2:** Wählen Sie bei "Antrag auf" → **"Einstellung"** aus
3. Klicken Sie auf "Weiter ➡️"
4. **Section 3:** Sie sind jetzt bei "Angaben zur einzustellenden/betreffenden Person"

### 4️⃣ **Debug-Info prüfen**

Oben auf der Seite erscheint ein Bereich "🐛 Debug Info". Klicken Sie darauf und prüfen Sie:

```json
{
  "antrag.typ": "einstellung",  // ← Muss "einstellung" sein!
  ...
}
```

### 5️⃣ **Scrollen Sie nach unten**

Suchen Sie nach den Debug-Expandern:

- 🔍 Debug: person.neueinstellung.fruehereBeschaeftigung.vorhanden
- 🔍 Debug: person.neueinstellung.fruehereBeschaeftigung.details

Klicken Sie darauf und sehen Sie:

```
🔍 Prüfe: antrag.typ (Wert: einstellung) = einstellung
   ➡️ Ergebnis: True oder False?
```

## 🎯 Mögliche Fehlerursachen

### **Fehler 1: `antrag.typ` ist nicht gesetzt**

**Symptom:**
```
🔍 Prüfe: antrag.typ (Wert: None) = einstellung
   ➡️ Ergebnis: False
```

**Lösung:**
- Gehen Sie zurück zu Section "Antrag auf"
- Wählen Sie "Einstellung" aus dem Dropdown
- Warten Sie kurz (Streamlit speichert automatisch)
- Gehen Sie wieder vorwärts

### **Fehler 2: Wert stimmt nicht überein**

**Symptom:**
```
🔍 Prüfe: antrag.typ (Wert: "Einstellung") = einstellung
   ➡️ Ergebnis: False
```

**Grund:** Der gespeicherte Wert ist "Einstellung" (mit großem E), aber erwartet wird "einstellung" (klein)

**Lösung:** In der data.json prüfen:
```json
"options": [
  { "value": "einstellung", "label": "Einstellung" }
]
```
Der `value` muss verwendet werden, nicht das `label`!

### **Fehler 3: Streamlit aktualisiert nicht**

**Symptom:** Felder erscheinen erst nach manuellem Reload

**Lösung:**
- Änderung in `render_field()` für `single_select`:
- Der Wert wird bereits gespeichert, aber Streamlit rendert nicht neu

**Fix:** Bereits implementiert! Bei single_select wird der Wert direkt in `form_data` gespeichert.

### **Fehler 4: Group wird doppelt geprüft**

**In Zeile 264-267 von app.py:**
```python
elif field_type == 'group':
    if self.should_show_field(field):  # ← REDUNDANT!
        st.markdown(f"**{label}**")
```

**Problem:** Die Prüfung erfolgt bereits in Zeile 132!

**Fix (optional):** Entfernen Sie die doppelte Prüfung:
```python
elif field_type == 'group':
    # showIf wurde bereits oben geprüft
    st.markdown(f"**{label}**")
    with st.container():
        for subfield in field.get('fields', []):
            self.render_field(subfield, section_id)
```

## 📊 Erwartete Debug-Ausgabe

### ✅ **Wenn alles funktioniert:**

```
🔍 Debug: person.neueinstellung.fruehereBeschaeftigung.vorhanden
Feld ID: person.neueinstellung.fruehereBeschaeftigung.vorhanden
Label: Bei Neueinstellung: Bestanden bereits Beschäftigungsverhältnisse...
ShowIf Bedingung:
{
  "field": "antrag.typ",
  "op": "=",
  "value": "einstellung"
}

🔍 Prüfe: antrag.typ (Wert: einstellung) = einstellung
   ➡️ Ergebnis: True ✅

[Das Feld wird angezeigt]
```

### ❌ **Wenn es nicht funktioniert:**

```
🔍 Prüfe: antrag.typ (Wert: None) = einstellung
   ➡️ Ergebnis: False ❌

[Das Feld wird NICHT angezeigt]
```

## 🛠️ Schnelltest

Führen Sie diesen Test aus:

```python
# In Python-Console oder neuem Fenster:
python test_conditions.py
```

Erwartete Ausgabe:
```
✅ PASS - Neueinstellung Feld sollte erscheinen
✅ PASS - Neueinstellung Feld sollte NICHT erscheinen
✅ PASS - Frühere Beschäftigung Details sollte erscheinen
✅ PASS - Frühere Beschäftigung Details sollte NICHT erscheinen
```

## 📝 Zusammenfassung

Die wahrscheinlichsten Probleme sind:

1. **`antrag.typ` wird nicht korrekt gespeichert** ← Häufigster Fehler!
2. **Streamlit aktualisiert die UI nicht automatisch**
3. **Bedingung in data.json stimmt nicht mit gespeichertem Wert überein**

Mit dem Debug-Modus können Sie **genau sehen**, welches Problem vorliegt!

## 🚀 Nächste Schritte

1. ✅ App starten: `streamlit run app.py`
2. ✅ Debug-Modus aktivieren (Sidebar)
3. ✅ "Einstellung" auswählen
4. ✅ Debug-Ausgabe lesen
5. 📧 Teilen Sie mir das Ergebnis mit!

Die Debug-Informationen zeigen Ihnen **exakt**, welches Feld welchen Wert hat und warum eine Bedingung True oder False ist.
