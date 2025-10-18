import streamlit as st
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from ollama_chat import OllamaChat
from pdf_generator import PDFGenerator

# Seitenkonfiguration
st.set_page_config(
    page_title="THWS Antragsformular",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS für besseres Design
st.markdown("""
<style>
    .main {
        padding: 0rem 1rem;
    }
    .stButton>button {
        width: 100%;
        background-color: #0066cc;
        color: white;
        border-radius: 8px;
        padding: 0.5rem 1rem;
        border: none;
        font-weight: 600;
    }
    .stButton>button:hover {
        background-color: #0052a3;
    }
    .section-header {
        background: linear-gradient(90deg, #0066cc 0%, #0052a3 100%);
        color: white;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
        font-weight: bold;
        font-size: 1.2rem;
    }
    .field-label {
        font-weight: 600;
        color: #333;
        margin-bottom: 0.5rem;
    }
    .help-text {
        font-size: 0.9rem;
        color: #666;
        font-style: italic;
        margin-top: 0.25rem;
    }
    .progress-bar {
        background-color: #e0e0e0;
        border-radius: 10px;
        height: 20px;
        margin: 1rem 0;
    }
    .progress-fill {
        background: linear-gradient(90deg, #00cc66 0%, #0066cc 100%);
        height: 100%;
        border-radius: 10px;
        transition: width 0.3s ease;
    }
    .completed-section {
        color: #00cc66;
    }
    .current-section {
        color: #0066cc;
        font-weight: bold;
    }
    
    /* Chat Assistant Styles */
    .chat-toggle-button {
        position: fixed;
        left: 20px;
        bottom: 20px;
        width: 60px;
        height: 60px;
        border-radius: 50%;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border: none;
        cursor: pointer;
        box-shadow: 0 4px 12px rgba(0,0,0,0.2);
        z-index: 1000;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: all 0.3s ease;
    }
    .chat-toggle-button:hover {
        transform: scale(1.1);
        box-shadow: 0 6px 16px rgba(0,0,0,0.3);
    }
    .chat-message-user {
        background-color: #0066cc;
        color: white;
        padding: 0.75rem;
        border-radius: 12px;
        margin: 0.5rem 0;
        max-width: 80%;
        margin-left: auto;
        word-wrap: break-word;
    }
    .chat-message-assistant {
        background-color: #f0f2f6;
        color: #333;
        padding: 0.75rem;
        border-radius: 12px;
        margin: 0.5rem 0;
        max-width: 80%;
        word-wrap: break-word;
    }
    .chat-container {
        border: 2px solid #667eea;
        border-radius: 12px;
        padding: 1rem;
        background-color: white;
        max-height: 500px;
        overflow-y: auto;
    }
</style>
""", unsafe_allow_html=True)

class FormFlow:
    def __init__(self, data_path: str = "data.json"):
        """Initialisiere den Form Flow mit den Daten aus data.json"""
        with open(data_path, 'r', encoding='utf-8') as f:
            self.data = json.load(f)
        
        # Session State initialisieren
        if 'form_data' not in st.session_state:
            st.session_state.form_data = {}
        if 'current_section' not in st.session_state:
            st.session_state.current_section = 0
        if 'completed_sections' not in st.session_state:
            st.session_state.completed_sections = set()
        if 'chat_visible' not in st.session_state:
            st.session_state.chat_visible = False
        if 'chat_history' not in st.session_state:
            st.session_state.chat_history = []
        if 'ollama_chat' not in st.session_state:
            st.session_state.ollama_chat = OllamaChat(
                base_url="YOUR_OLLAMA_SERVER_ENDPOINT",
                model="mistral-small3.2"
            )
    
    def evaluate_condition(self, condition: Dict[str, Any], debug: bool = False) -> bool:
        """Wertet eine Bedingung aus (showIf)"""
        if not condition:
            return True
        
        # Einzelne Feldbedingung
        if 'field' in condition:
            field_value = st.session_state.form_data.get(condition['field'])
            op = condition.get('op', '=')
            target = condition.get('value')
            
            if debug:
                st.write(f"🔍 Prüfe: `{condition['field']}` (Wert: `{field_value}`) {op} `{target}`")
            
            if op == '=':
                result = field_value == target
            elif op == '!=':
                result = field_value != target
            elif op == 'blank':
                result = not field_value
            elif op == '!blank':
                result = bool(field_value)
            else:
                result = False
            
            if debug:
                st.write(f"   ➡️ Ergebnis: {result}")
            
            return result
        
        # anyOf Bedingung
        if 'anyOf' in condition:
            if debug:
                st.write("🔀 anyOf Bedingung (mindestens eine muss erfüllt sein):")
            results = [self.evaluate_condition(c, debug) for c in condition['anyOf']]
            result = any(results)
            if debug:
                st.write(f"   ➡️ anyOf Ergebnis: {result}")
            return result
        
        # allOf Bedingung
        if 'allOf' in condition:
            if debug:
                st.write("🔗 allOf Bedingung (alle müssen erfüllt sein):")
            results = [self.evaluate_condition(c, debug) for c in condition['allOf']]
            result = all(results)
            if debug:
                st.write(f"   ➡️ allOf Ergebnis: {result}")
            return result
        
        return True
    
    def should_show_field(self, field: Dict[str, Any]) -> bool:
        """Prüft, ob ein Feld angezeigt werden soll"""
        if 'showIf' not in field:
            return True
        return self.evaluate_condition(field['showIf'])
    
    def render_field(self, field: Dict[str, Any], section_id: str) -> None:
        """Rendert ein einzelnes Feld basierend auf seinem Typ"""
        field_id = field['id']
        label = field.get('label', '')
        required = field.get('required', False)
        help_text = field.get('help', '')
        
        # Debug-Modus für bedingte Felder
        if st.session_state.get('debug_mode', False) and 'showIf' in field:
            with st.expander(f"🔍 Debug: {field_id}", expanded=False):
                st.write(f"**Feld ID:** `{field_id}`")
                st.write(f"**Label:** {label}")
                st.write(f"**ShowIf Bedingung:**")
                st.json(field['showIf'])
                self.evaluate_condition(field['showIf'], debug=True)
        
        # Prüfe ob Feld angezeigt werden soll
        if not self.should_show_field(field):
            return
        
        # Label mit required Markierung
        label_html = f"{'🔴 ' if required else ''}{label}"
        
        field_type = field['type']
        
        # Text Input
        if field_type == 'text':
            value = st.text_input(
                label_html,
                value=st.session_state.form_data.get(field_id, ''),
                key=field_id,
                help=help_text if help_text else None
            )
            st.session_state.form_data[field_id] = value
        
        # Textarea
        elif field_type == 'textarea':
            value = st.text_area(
                label_html,
                value=st.session_state.form_data.get(field_id, ''),
                key=field_id,
                help=help_text if help_text else None
            )
            st.session_state.form_data[field_id] = value
        
        # Email Input
        elif field_type == 'email':
            value = st.text_input(
                label_html,
                value=st.session_state.form_data.get(field_id, ''),
                key=field_id,
                help=help_text if help_text else None,
                placeholder="beispiel@thws.de"
            )
            st.session_state.form_data[field_id] = value
        
        # Date Input
        elif field_type == 'date':
            existing_value = st.session_state.form_data.get(field_id)
            if existing_value and isinstance(existing_value, str):
                try:
                    existing_value = datetime.strptime(existing_value, '%Y-%m-%d').date()
                except:
                    existing_value = None
            
            value = st.date_input(
                label_html,
                value=existing_value,
                key=field_id,
                help=help_text if help_text else None
            )
            st.session_state.form_data[field_id] = value.strftime('%Y-%m-%d') if value else None
        
        # Single Select
        elif field_type == 'single_select':
            options = field.get('options', [])
            option_values = [opt['value'] for opt in options]
            option_labels = [opt['label'] for opt in options]
            
            current_value = st.session_state.form_data.get(field_id)
            index = option_values.index(current_value) if current_value in option_values else 0
            
            selected_label = st.selectbox(
                label_html,
                options=option_labels,
                index=index,
                key=f"{field_id}_select",
                help=help_text if help_text else None
            )
            
            selected_index = option_labels.index(selected_label)
            st.session_state.form_data[field_id] = option_values[selected_index]
        
        # Multi Select
        elif field_type == 'multi_select':
            options = field.get('options', [])
            option_values = [opt['value'] for opt in options]
            option_labels = [opt['label'] for opt in options]
            
            current_values = st.session_state.form_data.get(field_id, [])
            default_indices = [i for i, v in enumerate(option_values) if v in current_values]
            default_labels = [option_labels[i] for i in default_indices]
            
            selected_labels = st.multiselect(
                label_html,
                options=option_labels,
                default=default_labels,
                key=f"{field_id}_multi",
                help=help_text if help_text else None
            )
            
            selected_values = [option_values[option_labels.index(lbl)] for lbl in selected_labels]
            st.session_state.form_data[field_id] = selected_values
        
        # Number Input
        elif field_type == 'number':
            min_val = field.get('min', 0)
            max_val = field.get('max', 100)
            value = st.number_input(
                label_html,
                min_value=min_val,
                max_value=max_val,
                value=st.session_state.form_data.get(field_id, min_val),
                key=field_id,
                help=help_text if help_text else None
            )
            st.session_state.form_data[field_id] = value
        
        # Boolean
        elif field_type == 'boolean':
            value = st.checkbox(
                label_html,
                value=st.session_state.form_data.get(field_id, False),
                key=field_id,
                help=help_text if help_text else None
            )
            st.session_state.form_data[field_id] = value
        
        # Acknowledgement
        elif field_type == 'acknowledgement':
            value = st.checkbox(
                label_html,
                value=st.session_state.form_data.get(field_id, False),
                key=field_id,
                help=help_text if help_text else None
            )
            st.session_state.form_data[field_id] = value
        
        # Group (verschachtelte Felder)
        elif field_type == 'group':
            # showIf wurde bereits am Anfang von render_field() geprüft
            st.markdown(f"**{label}**")
            with st.container():
                for subfield in field.get('fields', []):
                    self.render_field(subfield, section_id)
        
        # Date Range
        elif field_type == 'date_range':
            col1, col2 = st.columns(2)
            with col1:
                start_date = st.date_input(
                    f"{label} (Von)",
                    key=f"{field_id}_start",
                    help=help_text if help_text else None
                )
            with col2:
                end_date = st.date_input(
                    f"{label} (Bis)",
                    key=f"{field_id}_end"
                )
            st.session_state.form_data[field_id] = {
                'start': start_date.strftime('%Y-%m-%d') if start_date else None,
                'end': end_date.strftime('%Y-%m-%d') if end_date else None
            }
        
        # Repeating Group
        elif field_type == 'repeating_group':
            st.markdown(f"**{label}**")
            
            if field_id not in st.session_state.form_data:
                st.session_state.form_data[field_id] = []
            
            items = st.session_state.form_data[field_id]
            
            for i, item in enumerate(items):
                with st.expander(f"{field.get('itemLabel', 'Item')} {i+1}", expanded=True):
                    for subfield in field.get('fields', []):
                        subfield_id = f"{field_id}[{i}].{subfield['id']}"
                        subfield_copy = subfield.copy()
                        subfield_copy['id'] = subfield_id
                        self.render_field(subfield_copy, section_id)
                    
                    if st.button(f"❌ Entfernen", key=f"remove_{field_id}_{i}"):
                        items.pop(i)
                        st.rerun()
            
            if st.button(f"➕ {field.get('itemLabel', 'Item')} hinzufügen", key=f"add_{field_id}"):
                items.append({})
                st.rerun()
    
    def validate_section(self, section: Dict[str, Any]) -> tuple[bool, List[str]]:
        """Validiert eine Section und gibt zurück ob gültig und Liste der Fehler"""
        errors = []
        
        for field in section.get('fields', []):
            if not self.should_show_field(field):
                continue
            
            field_id = field['id']
            required = field.get('required', False)
            
            if required:
                value = st.session_state.form_data.get(field_id)
                if not value:
                    errors.append(f"'{field.get('label', field_id)}' ist erforderlich")
            
            # Rekursive Validierung für Groups
            if field['type'] == 'group':
                for subfield in field.get('fields', []):
                    if not self.should_show_field(subfield):
                        continue
                    if subfield.get('required') and not st.session_state.form_data.get(subfield['id']):
                        errors.append(f"'{subfield.get('label', subfield['id'])}' ist erforderlich")
        
        return len(errors) == 0, errors
    
    def evaluate_required_if(self, condition: Dict[str, Any]) -> bool:
        """Wertet eine requiredIf-Bedingung für Checklisten-Items aus"""
        if not condition:
            return False
        
        # Always-Bedingung
        if condition.get('always'):
            return True
        
        # existsInAny für Array-Felder mit Pattern-Matching
        if 'existsInAny' in condition:
            exists_check = condition['existsInAny']
            array_field_path = exists_check.get('arrayField', '')
            pattern = exists_check.get('pattern', '')
            
            # Extrahiere den Array-Feldnamen (z.B. "finanzierung.zeilen")
            # aus "finanzierung.zeilen[].fin.titel"
            if '[].' in array_field_path:
                array_base, sub_field = array_field_path.split('[].')
                array_data = st.session_state.form_data.get(array_base, [])
                
                if isinstance(array_data, list):
                    import re
                    for item in array_data:
                        # Extrahiere den Wert aus dem verschachtelten Feld
                        field_value = item.get(sub_field, '')
                        if field_value and re.search(pattern, str(field_value)):
                            return True
            return False
        
        # Einzelne Feldbedingung (wie bei showIf)
        if 'field' in condition:
            return self.evaluate_condition(condition)
        
        # anyOf Bedingung
        if 'anyOf' in condition:
            return any(self.evaluate_required_if(c) for c in condition['anyOf'])
        
        # allOf Bedingung
        if 'allOf' in condition:
            return all(self.evaluate_required_if(c) for c in condition['allOf'])
        
        return False
    
    def render_checklist_section(self, section: Dict[str, Any]):
        """Rendert eine Checklisten-Section (type: derived)"""
        st.markdown("### 📋 Erforderliche Unterlagen")
        
        items = section.get('items', [])
        
        if not items:
            st.info("Keine Checklisten-Items definiert.")
            return
        
        # Gruppiere Items nach erforderlich/optional
        required_items = []
        optional_items = []
        
        for item in items:
            item_id = item.get('id')
            label = item.get('label', item_id)
            required_if = item.get('requiredIf', {})
            
            is_required = self.evaluate_required_if(required_if)
            
            if is_required:
                required_items.append((item_id, label, required_if))
            else:
                optional_items.append((item_id, label, required_if))
        
        # Zeige erforderliche Unterlagen
        if required_items:
            st.markdown("#### ✅ Erforderliche Unterlagen")
            st.markdown("Diese Unterlagen müssen dem Antrag beigefügt werden:")
            
            for item_id, label, required_if in required_items:
                # Checkbox für "erledigt"
                checked = st.session_state.form_data.get(f"checklist.{item_id}", False)
                
                col1, col2 = st.columns([0.1, 0.9])
                with col1:
                    is_checked = st.checkbox(
                        "",
                        value=checked,
                        key=f"checklist_{item_id}",
                        label_visibility="collapsed"
                    )
                    st.session_state.form_data[f"checklist.{item_id}"] = is_checked
                
                with col2:
                    st.markdown(f"**{label}**")
                    # Zeige Begründung warum erforderlich
                    if st.session_state.get('debug_mode', False):
                        with st.expander("🔍 Debug: Warum erforderlich?", expanded=False):
                            st.json(required_if)
        else:
            st.info("ℹ️ Basierend auf Ihren Angaben sind aktuell keine zusätzlichen Unterlagen erforderlich (außer dem Standardformular).")
        
        # Zeige nicht erforderliche Unterlagen (optional)
        if optional_items and st.session_state.get('debug_mode', False):
            with st.expander("ℹ️ Aktuell nicht erforderliche Unterlagen", expanded=False):
                st.markdown("Diese Unterlagen sind basierend auf Ihren Angaben aktuell **nicht** erforderlich:")
                for item_id, label, required_if in optional_items:
                    st.markdown(f"- {label}")
    
    # ...existing code...
    def render_progress_bar(self):
        """Rendert eine Fortschrittsanzeige"""
        sections = self.data['root']['sections']
        total = len(sections)
        completed = len(st.session_state.completed_sections)
        current = st.session_state.current_section
        
        progress = (completed / total) * 100
        
        st.markdown(f"""
        <div class="progress-bar">
            <div class="progress-fill" style="width: {progress}%"></div>
        </div>
        <p style="text-align: center; color: #666;">
            Abschnitt {current + 1} von {total} | {completed} abgeschlossen
        </p>
        """, unsafe_allow_html=True)
    
    def render_sidebar_navigation(self):
        """Rendert die Navigation in der Sidebar"""
        st.sidebar.title("📋 Navigation")
        
        # Debug Mode Toggle
        st.session_state.debug_mode = st.sidebar.checkbox("🐛 Debug Modus", value=st.session_state.get('debug_mode', False))
        
        st.sidebar.markdown("---")
        
        sections = self.data['root']['sections']
        current = st.session_state.current_section
        
        for idx, section in enumerate(sections):
            icon = "✅" if idx in st.session_state.completed_sections else ("🔵" if idx == current else "⚪")
            css_class = "completed-section" if idx in st.session_state.completed_sections else ("current-section" if idx == current else "")
            
            if st.sidebar.button(
                f"{icon} {section.get('title', f'Section {idx+1}')}",
                key=f"nav_{idx}",
                use_container_width=True
            ):
                st.session_state.current_section = idx
                st.rerun()
        
        st.sidebar.markdown("---")
        
        # Chat Assistant Toggle
        chat_icon = "🤖 💬" if st.session_state.chat_visible else "🤖 💬"
        if st.sidebar.button(f"{chat_icon} Chat-Assistent", use_container_width=True):
            st.session_state.chat_visible = not st.session_state.chat_visible
            st.rerun()
        
        st.sidebar.markdown("---")
        
        # Download Button für JSON
        if st.sidebar.button("💾 Formular als JSON speichern", use_container_width=True):
            json_str = json.dumps(st.session_state.form_data, indent=2, ensure_ascii=False)
            st.sidebar.download_button(
                label="📥 Download JSON",
                data=json_str,
                file_name=f"antrag_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )
    
    def render_chat_assistant(self):
        """Rendert den Chat-Assistenten"""
        if not st.session_state.chat_visible:
            return
        
        st.markdown("---")
        st.markdown("### 🤖 Chat-Assistent")
        
        # Verbindungsstatus prüfen
        with st.expander("ℹ️ Verbindungsinformationen", expanded=False):
            ollama = st.session_state.ollama_chat
            st.write(f"**Server:** {ollama.base_url}")
            st.write(f"**Modell:** {ollama.model}")
            
            if st.button("🔄 Verbindung testen", key="test_connection"):
                with st.spinner("Teste Verbindung..."):
                    success, message = ollama.check_connection()
                    if success:
                        st.success(message)
                    else:
                        st.error(message)
            
            if st.button("🗑️ Konversation zurücksetzen", key="reset_chat"):
                st.session_state.ollama_chat.reset_conversation()
                st.session_state.chat_history = []
                st.success("Chat-Historie wurde zurückgesetzt!")
                st.rerun()
        
        # Chat-Container
        chat_container = st.container()
        
        with chat_container:
            st.markdown('<div class="chat-container">', unsafe_allow_html=True)
            
            # Zeige Chat-Historie
            if not st.session_state.chat_history:
                st.info("👋 Hallo! Ich bin Ihr Assistent für das THWS-Antragsformular. Wie kann ich Ihnen helfen?")
            else:
                for msg in st.session_state.chat_history:
                    if msg["role"] == "user":
                        st.markdown(f'<div class="chat-message-user">👤 {msg["content"]}</div>', unsafe_allow_html=True)
                    else:
                        st.markdown(f'<div class="chat-message-assistant">🤖 {msg["content"]}</div>', unsafe_allow_html=True)
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        # Chat-Input
        st.markdown("---")
        
        # Verwende Spalten für besseres Layout
        col1, col2 = st.columns([5, 1])
        
        with col1:
            user_message = st.text_input(
                "Ihre Frage:",
                key="chat_input",
                placeholder="Stellen Sie eine Frage zum Formular...",
                label_visibility="collapsed"
            )
        
        with col2:
            send_button = st.button("📤 Senden", use_container_width=True, key="send_message")
        
        # Sende Nachricht wenn Button geklickt oder Enter gedrückt
        if send_button and user_message:
            # Füge Benutzernachricht zur Historie hinzu
            st.session_state.chat_history.append({
                "role": "user",
                "content": user_message
            })
            
            # System-Prompt mit Kontext über das Formular
            system_prompt = f"""Du bist ein hilfreicher Assistent für das THWS-Antragsformular zur Einstellung/Weiterbeschäftigung/Arbeitszeitänderung.

Formular-Kontext:
- Formulartitel: {self.data['meta']['title']}
- Version: {self.data['meta']['version']}
- Anzahl Sections: {len(self.data['root']['sections'])}

Der Benutzer füllt gerade ein Formular aus. Hier sind die bisher eingegebenen Daten:
{json.dumps(st.session_state.form_data, indent=2, ensure_ascii=False)}

Beantworte Fragen zum Formular, erkläre Felder, helfe bei Unklarheiten und gib Tipps zum Ausfüllen.
Antworte auf Deutsch und sei präzise und hilfreich."""
            
            # Zeige "Tippt..." Nachricht
            with st.spinner("🤖 Assistent tippt..."):
                # Sammle die Antwort
                response_text = ""
                response_placeholder = st.empty()
                
                try:
                    for chunk in st.session_state.ollama_chat.chat_stream(user_message, system_prompt):
                        response_text += chunk
                        # Aktualisiere die Anzeige während des Streamings
                        response_placeholder.markdown(f'<div class="chat-message-assistant">🤖 {response_text}</div>', unsafe_allow_html=True)
                    
                    # Füge Antwort zur Historie hinzu
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": response_text
                    })
                    
                    # Leere die Platzhalter und rerun
                    response_placeholder.empty()
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ Fehler beim Chat: {str(e)}")
                    st.info("💡 Tipp: Stellen Sie sicher, dass der Ollama-Server erreichbar ist.")
    
    def render_current_section(self):
        """Rendert die aktuelle Section"""
        sections = self.data['root']['sections']
        current_idx = st.session_state.current_section
        
        if current_idx >= len(sections):
            self.render_summary()
            return
        
        section = sections[current_idx]
        
        # Section Header
        st.markdown(f'<div class="section-header">{section.get("title", "")}</div>', unsafe_allow_html=True)
        
        # Debug Mode Toggle in Sidebar
        if 'debug_mode' not in st.session_state:
            st.session_state.debug_mode = False
        
        # Debug Anzeige
        if st.session_state.debug_mode:
            with st.expander("🐛 Debug Info", expanded=False):
                st.write("**Aktuelle Form-Daten:**")
                st.json(st.session_state.form_data)
                st.write(f"**Aktuelle Section:** {section.get('id')}")
                st.write(f"**Section Type:** {section.get('type', 'standard')}")
                st.write(f"**Anzahl Felder in Section:** {len(section.get('fields', []))}")
                st.write(f"**Anzahl Items in Section:** {len(section.get('items', []))}")
        
        # Prüfe Section Type
        section_type = section.get('type', 'standard')
        
        if section_type == 'derived':
            # Render Checkliste (derived section)
            self.render_checklist_section(section)
        else:
            # Felder rendern (normale Section)
            for field in section.get('fields', []):
                self.render_field(field, section['id'])
        
        # Navigation Buttons
        col1, col2, col3 = st.columns([1, 1, 1])
        
        with col1:
            if current_idx > 0:
                if st.button("⬅️ Zurück", use_container_width=True):
                    st.session_state.current_section -= 1
                    st.rerun()
        
        with col2:
            # Validieren Button
            is_valid, errors = self.validate_section(section)
            if errors:
                st.warning(f"⚠️ {len(errors)} Fehler gefunden")
                with st.expander("Fehlerdetails anzeigen"):
                    for error in errors:
                        st.error(error)
        
        with col3:
            if current_idx < len(sections) - 1:
                if st.button("Weiter ➡️", use_container_width=True):
                    is_valid, errors = self.validate_section(section)
                    if is_valid:
                        st.session_state.completed_sections.add(current_idx)
                        st.session_state.current_section += 1
                        st.rerun()
                    else:
                        st.error("Bitte füllen Sie alle erforderlichen Felder aus.")
            else:
                if st.button("✅ Abschließen", use_container_width=True):
                    is_valid, errors = self.validate_section(section)
                    if is_valid:
                        st.session_state.completed_sections.add(current_idx)
                        st.session_state.current_section = len(sections)
                        st.rerun()
                    else:
                        st.error("Bitte füllen Sie alle erforderlichen Felder aus.")
    
    def render_summary(self):
        """Rendert eine Zusammenfassung aller eingegebenen Daten"""
        st.success("🎉 Formular vollständig ausgefüllt!")
        
        st.markdown("## 📊 Zusammenfassung")
        
        sections = self.data['root']['sections']
        
        for section in sections:
            with st.expander(f"📄 {section.get('title', '')}", expanded=False):
                for field in section.get('fields', []):
                    self.render_summary_field(field)
        
        # Aktionen
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if st.button("🔄 Formular zurücksetzen", use_container_width=True):
                st.session_state.form_data = {}
                st.session_state.current_section = 0
                st.session_state.completed_sections = set()
                st.rerun()
        
        with col2:
            json_str = json.dumps(st.session_state.form_data, indent=2, ensure_ascii=False)
            st.download_button(
                label="💾 JSON herunterladen",
                data=json_str,
                file_name=f"antrag_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                use_container_width=True
            )
        
        with col3:
            # PDF Export Button
            try:
                pdf_gen = PDFGenerator(template_path="template_simple.html")
                pdf_bytes = pdf_gen.generate_pdf(st.session_state.form_data)
                filename = pdf_gen.get_filename(st.session_state.form_data)
                
                st.download_button(
                    label="📄 PDF herunterladen",
                    data=pdf_bytes,
                    file_name=filename,
                    mime="application/pdf",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"PDF-Generierung fehlgeschlagen: {str(e)}")
                if st.button("🔍 Details anzeigen", key="pdf_error_details", use_container_width=True):
                    st.exception(e)
        
        with col4:
            if st.button("📧 Antrag absenden", use_container_width=True):
                st.success("✅ Antrag erfolgreich abgesendet! (Demo)")
    
    def render_summary_field(self, field: Dict[str, Any], indent: int = 0):
        """Rendert ein Feld in der Zusammenfassung"""
        field_id = field['id']
        value = st.session_state.form_data.get(field_id)
        
        if not value:
            return
        
        label = field.get('label', field_id)
        indent_str = "&nbsp;" * (indent * 4)
        
        if field['type'] == 'group':
            st.markdown(f"{indent_str}**{label}**")
            for subfield in field.get('fields', []):
                self.render_summary_field(subfield, indent + 1)
        else:
            st.markdown(f"{indent_str}**{label}:** {value}")
    
    def run(self):
        """Hauptfunktion zum Ausführen der App"""
        # Header
        meta = self.data.get('meta', {})
        st.title(f"📝 {meta.get('title', 'Formular')}")
        st.caption(f"Version: {meta.get('version', 'N/A')} | {meta.get('locale', 'de-DE')}")
        
        # Sidebar Navigation
        self.render_sidebar_navigation()
        
        # Chat-Assistent (wenn aktiviert)
        if st.session_state.chat_visible:
            # Verwende Spalten für Layout: Chat links, Formular rechts
            col_chat, col_form = st.columns([1, 2])
            
            with col_chat:
                self.render_chat_assistant()
            
            with col_form:
                # Fortschrittsbalken
                self.render_progress_bar()
                
                # Aktuelle Section rendern
                self.render_current_section()
        else:
            # Fortschrittsbalken
            self.render_progress_bar()
            
            # Aktuelle Section rendern
            self.render_current_section()

# App starten
if __name__ == "__main__":
    app = FormFlow()
    app.run()
