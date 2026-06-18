# HAUPTZIEL

**Plan hochladen → Raum auswählen → Wand auswählen → Ergebnis mit Ausrechnung.**

Der Kern-Workflow (das, woran die Lösung gemessen wird):

1. **Plan hochladen** (Grundriss, PDF/Bild — auch echte Ausführungspläne)
2. **Raum wählen** (aus den extrahierten Räumen)
3. **Wand wählen** (eine Wand dieses Raums)
4. **Ergebnis mit Ausrechnung** anzeigen: der vollständige DIN-4109-Rechengang für genau dieses Bauteil
   (m′ → R′w / L′n,w → Abgleich gegen erf./zul. Wert → erfüllt / nicht erfüllt), transparent nachvollziehbar.

Alles andere (Batch-Nachweis aller Bauteile, Reports, Exporte) ist Beiwerk — dieser
interaktive Einzel-Auswahl-Flow mit sichtbarer Berechnung ist das Zentrum der Demo.

## Bausteine, die dafür schon stehen
- Extraktion Plan → Modell (`extraction/`: Einzelbild + gekachelt für echte Pläne)
- Engine `berechne_bauteil()` rechnet bereits pro Bauteil den vollen Rechengang
- Rechengang-Excel zeigt die Ausrechnung Zelle für Zelle

## Was für das Hauptziel noch fokussiert werden muss
- UI-Flow: nach Extraktion **Raum-Dropdown → Wand-Dropdown → Ergebniskarte** mit Live-Rechengang
  (statt nur der Gesamttabelle). Das ist die nächste Ausbaustufe.
