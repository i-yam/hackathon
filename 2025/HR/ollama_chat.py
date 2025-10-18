"""
Ollama Chat Integration für Streamlit
Verbindet mit einem Ollama Server und ermöglicht Chat-Interaktion
"""

import requests
import json
from typing import List, Dict, Generator, Optional

class OllamaChat:
    def __init__(self, base_url: str = "YOUR_OLLAMA_SERVER_ENDPOINT", model: str = "mistral-small3.2"):
        """
        Initialisiert den Ollama Chat Client
        
        Args:
            base_url: Die Basis-URL des Ollama Servers
            model: Das zu verwendende Modell
        """
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.conversation_history: List[Dict[str, str]] = []
    
    def check_connection(self) -> tuple[bool, str]:
        """
        Prüft die Verbindung zum Ollama Server
        
        Returns:
            (success, message): Tuple mit Erfolg und Nachricht
        """
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                data = response.json()
                models = [m['name'] for m in data.get('models', [])]
                return True, f"✅ Verbunden! Verfügbare Modelle: {', '.join(models)}"
            else:
                return False, f"❌ Server antwortet mit Status {response.status_code}"
        except requests.exceptions.ConnectionError:
            return False, f"❌ Keine Verbindung zu {self.base_url} möglich"
        except requests.exceptions.Timeout:
            return False, "❌ Timeout beim Verbindungsversuch"
        except Exception as e:
            return False, f"❌ Fehler: {str(e)}"
    
    def chat_stream(self, message: str, system_prompt: Optional[str] = None) -> Generator[str, None, None]:
        """
        Sendet eine Nachricht und streamt die Antwort
        
        Args:
            message: Die Benutzernachricht
            system_prompt: Optionaler System-Prompt für Kontext
            
        Yields:
            Teile der Antwort als sie empfangen werden
        """
        # Füge Nachricht zur Historie hinzu
        self.conversation_history.append({
            "role": "user",
            "content": message
        })
        
        # Baue die Nachrichten-Liste auf
        messages = []
        
        # System-Prompt hinzufügen wenn vorhanden
        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt
            })
        
        # Konversations-Historie hinzufügen
        messages.extend(self.conversation_history)
        
        # API-Anfrage
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                stream=True,
                timeout=60
            )
            
            if response.status_code != 200:
                yield f"❌ Fehler: Server antwortete mit Status {response.status_code}"
                return
            
            # Sammle die vollständige Antwort
            full_response = ""
            
            # Stream die Antwort
            for line in response.iter_lines():
                if line:
                    try:
                        data = json.loads(line)
                        if 'message' in data and 'content' in data['message']:
                            chunk = data['message']['content']
                            full_response += chunk
                            yield chunk
                        
                        # Prüfe ob fertig
                        if data.get('done', False):
                            break
                    except json.JSONDecodeError:
                        continue
            
            # Füge Antwort zur Historie hinzu
            if full_response:
                self.conversation_history.append({
                    "role": "assistant",
                    "content": full_response
                })
        
        except requests.exceptions.Timeout:
            yield "❌ Timeout: Der Server antwortet nicht rechtzeitig."
        except requests.exceptions.ConnectionError:
            yield f"❌ Verbindungsfehler: Kann nicht mit {self.base_url} verbinden."
        except Exception as e:
            yield f"❌ Unerwarteter Fehler: {str(e)}"
    
    def chat(self, message: str, system_prompt: Optional[str] = None) -> str:
        """
        Sendet eine Nachricht und gibt die vollständige Antwort zurück
        
        Args:
            message: Die Benutzernachricht
            system_prompt: Optionaler System-Prompt für Kontext
            
        Returns:
            Die vollständige Antwort
        """
        full_response = ""
        for chunk in self.chat_stream(message, system_prompt):
            full_response += chunk
        return full_response
    
    def reset_conversation(self):
        """Setzt die Konversations-Historie zurück"""
        self.conversation_history = []
    
    def get_conversation_history(self) -> List[Dict[str, str]]:
        """Gibt die aktuelle Konversations-Historie zurück"""
        return self.conversation_history.copy()


def test_ollama_connection():
    """Testet die Verbindung zum Ollama Server"""
    print("=" * 60)
    print("OLLAMA CONNECTION TEST")
    print("=" * 60)
    
    chat = OllamaChat()
    success, message = chat.check_connection()
    print(f"\n{message}\n")
    
    if success:
        print("Teste Chat-Funktion...")
        print("-" * 60)
        
        response = chat.chat("Hallo! Kannst du mir in einem Satz sagen, wer du bist?")
        print(f"Antwort: {response}")
        print("-" * 60)
    
    print("\n" + "=" * 60)
    print("Test abgeschlossen!")
    print("=" * 60)


if __name__ == "__main__":
    test_ollama_connection()
