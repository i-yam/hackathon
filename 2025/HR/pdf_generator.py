"""
PDF Generator für THWS Antragsformular
Verwendet Jinja2 Template und xhtml2pdf für PDF-Generierung
"""

from jinja2 import Template, Environment, FileSystemLoader
from xhtml2pdf import pisa
from typing import Dict, Any
import os
from datetime import datetime
from io import BytesIO


class PDFGenerator:
    """Generiert PDF aus Formulardaten mit Jinja2-Template"""
    
    def __init__(self, template_path: str = "template.html"):
        """
        Initialisiere PDF-Generator
        
        Args:
            template_path: Pfad zum Jinja2-HTML-Template
        """
        self.template_path = template_path
        
        # Lade Template
        template_dir = os.path.dirname(os.path.abspath(template_path))
        template_file = os.path.basename(template_path)
        
        env = Environment(loader=FileSystemLoader(template_dir))
        self.template = env.get_template(template_file)
    
    def prepare_data(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Bereite Formulardaten für Template vor
        Konvertiert flache Struktur in verschachtelte Struktur
        
        Args:
            form_data: Flache Form-Daten aus Streamlit Session State
            
        Returns:
            Verschachtelte Datenstruktur für Template
        """
        data = {
            'absender': {},
            'antrag': {},
            'person': {
                'aufenthalt': {},
                'parallelbeschaeftigung': {},
                'neueinstellung': {
                    'fruehereBeschaeftigung': {}
                },
                'sb': {}
            },
            'vertrag': {
                'ausschreibungsverzicht': {},
                'beginn': {},
                'ende': {},
                'sachgrund': {},
                'vertretung': {}
            },
            'arbeit': {
                'teilzeit': {},
                'minijob': {}
            },
            'entgelt': {
                'eingruppierung': {},
                'verbeamtung': {}
            },
            'vorgesetzte': {
                'details': {}
            },
            'finanzierung': {
                'zeilen': []
            },
            'kenntnisnahme': {},
            'hspe': {
                'unterlagen': {},
                'angefordert': {},
                'pruefung': {}
            },
            'hspe_intern_anzeigen': False
        }
        
        # Mappe flache Keys zu verschachtelter Struktur
        for key, value in form_data.items():
            parts = key.split('.')
            
            # Überspringe leere Werte
            if not value:
                continue
            
            # Absender
            if key.startswith('absender.'):
                data['absender'][parts[1]] = value
            
            # Antrag
            elif key.startswith('antrag.'):
                data['antrag'][parts[1]] = value
            
            # Person
            elif key.startswith('person.'):
                if len(parts) == 2:
                    data['person'][parts[1]] = value
                elif parts[1] == 'aufenthalt':
                    data['person']['aufenthalt'][parts[2]] = value
                elif parts[1] == 'parallelbeschaeftigung':
                    if len(parts) == 3:
                        data['person']['parallelbeschaeftigung'][parts[2]] = value
                elif parts[1] == 'neueinstellung':
                    if parts[2] == 'fruehereBeschaeftigung':
                        if len(parts) == 4:
                            data['person']['neueinstellung']['fruehereBeschaeftigung'][parts[3]] = value
                elif parts[1] == 'sb':
                    data['person']['sb'][parts[2]] = value
            
            # Vertrag
            elif key.startswith('vertrag.'):
                if len(parts) == 2:
                    data['vertrag'][parts[1]] = value
                elif parts[1] == 'ausschreibungsverzicht':
                    data['vertrag']['ausschreibungsverzicht'][parts[2]] = value
                elif parts[1] == 'beginn' and len(parts) == 3:
                    data['vertrag']['beginn'][parts[2]] = value
                elif parts[1] == 'ende':
                    if len(parts) == 3:
                        data['vertrag']['ende'][parts[2]] = value
                elif parts[1] == 'sachgrund':
                    data['vertrag']['sachgrund'][parts[2]] = value
                elif parts[1] == 'vertretung':
                    data['vertrag']['vertretung'][parts[2]] = value
            
            # Arbeit
            elif key.startswith('arbeit.'):
                if len(parts) == 2:
                    data['arbeit'][parts[1]] = value
                elif parts[1] == 'teilzeit':
                    data['arbeit']['teilzeit'][parts[2]] = value
                elif parts[1] == 'minijob':
                    data['arbeit']['minijob'][parts[2]] = value
            
            # Entgelt
            elif key.startswith('entgelt.'):
                if parts[1] == 'eingruppierung':
                    data['entgelt']['eingruppierung'][parts[2]] = value
                elif parts[1] == 'verbeamtung':
                    data['entgelt']['verbeamtung'][parts[2]] = value
            
            # Vorgesetzte
            elif key.startswith('vorgesetzte.'):
                if len(parts) == 2:
                    data['vorgesetzte'][parts[1]] = value
                elif parts[1] == 'details':
                    data['vorgesetzte']['details'][parts[2]] = value
            
            # Dienstort
            elif key == 'dienstort':
                data['dienstort'] = value
            elif key == 'dienstort.sonstiger':
                data['dienstort_sonstiger'] = value
            
            # Finanzierung - Repeating Group
            elif key.startswith('finanzierung.zeilen'):
                # Extract index: finanzierung.zeilen[0].fin.anteil_prozent
                if '[' in key and ']' in key:
                    idx_start = key.index('[') + 1
                    idx_end = key.index(']')
                    idx = int(key[idx_start:idx_end])
                    
                    # Stelle sicher dass genug Items existieren
                    while len(data['finanzierung']['zeilen']) <= idx:
                        data['finanzierung']['zeilen'].append({'fin': {
                            'anteil_prozent': 0,
                            'kapitel': '',
                            'titel': '',
                            'mittelherkunft': {'fb_proj': '', 'ins_a_art': ''},
                            'mittelverwendung': {'kostenstelle': '', 'kostentraeger': ''}
                        }})
                    
                    # Extrahiere Subkey (z.B. fin.anteil_prozent)
                    subkey_parts = key[idx_end+2:].split('.')  # +2 für '].'
                    
                    if subkey_parts[0] == 'fin':
                        if len(subkey_parts) == 2:
                            data['finanzierung']['zeilen'][idx]['fin'][subkey_parts[1]] = value
                        elif len(subkey_parts) == 3:
                            if subkey_parts[1] not in data['finanzierung']['zeilen'][idx]['fin']:
                                data['finanzierung']['zeilen'][idx]['fin'][subkey_parts[1]] = {}
                            data['finanzierung']['zeilen'][idx]['fin'][subkey_parts[1]][subkey_parts[2]] = value
            
            elif key == 'finanzierung.bei_drittmitteln':
                data['finanzierung']['bei_drittmitteln'] = value
            
            # Kenntnisnahme
            elif key.startswith('kenntnisnahme.'):
                data['kenntnisnahme'][parts[1]] = value
            
            # HSPE
            elif key.startswith('hspe.'):
                data['hspe_intern_anzeigen'] = True
                if len(parts) == 2:
                    data['hspe'][parts[1]] = value
                elif parts[1] == 'unterlagen':
                    data['hspe']['unterlagen'][parts[2]] = value
                elif parts[1] == 'angefordert':
                    data['hspe']['angefordert'][parts[2]] = value
                elif parts[1] == 'pruefung':
                    data['hspe']['pruefung'][parts[2]] = value
        
        return data
    
    def generate_html(self, form_data: Dict[str, Any]) -> str:
        """
        Generiere HTML aus Formulardaten
        
        Args:
            form_data: Formulardaten
            
        Returns:
            Gerenderte HTML-String
        """
        data = self.prepare_data(form_data)
        # Füge Generierungsdatum hinzu
        data['generierungsdatum'] = datetime.now().strftime('%d.%m.%Y %H:%M')
        return self.template.render(**data)
    
    def generate_pdf(self, form_data: Dict[str, Any], output_path: str = None) -> bytes:
        """
        Generiere PDF aus Formulardaten
        
        Args:
            form_data: Formulardaten
            output_path: Optional - Pfad zum Speichern der PDF
            
        Returns:
            PDF als Bytes
        """
        html_content = self.generate_html(form_data)
        
        # Erstelle BytesIO-Objekt für PDF-Output
        pdf_buffer = BytesIO()
        
        # Generiere PDF mit xhtml2pdf
        pisa_status = pisa.CreatePDF(
            src=html_content,
            dest=pdf_buffer,
            encoding='utf-8'
        )
        
        # Hole PDF-Bytes
        pdf_bytes = pdf_buffer.getvalue()
        pdf_buffer.close()
        
        # Prüfe auf Fehler
        if pisa_status.err:
            raise Exception(f"PDF-Generierung fehlgeschlagen: {pisa_status.err} Fehler")
        
        # Optional: Speichere in Datei
        if output_path:
            with open(output_path, 'wb') as f:
                f.write(pdf_bytes)
        
        return pdf_bytes
    
    def get_filename(self, form_data: Dict[str, Any]) -> str:
        """
        Generiere Dateinamen basierend auf Formulardaten
        
        Args:
            form_data: Formulardaten
            
        Returns:
            Dateiname für PDF
        """
        # Extrahiere relevante Infos
        nachname = form_data.get('person.nachname', 'unbekannt')
        vorname = form_data.get('person.vorname', '')
        antrag_typ = form_data.get('antrag.typ', 'antrag')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Erstelle Dateinamen
        name = f"{nachname}_{vorname}".replace(' ', '_') if vorname else nachname
        filename = f"THWS_Antrag_{antrag_typ}_{name}_{timestamp}.pdf"
        
        return filename
