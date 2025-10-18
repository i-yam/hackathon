@echo off
echo ========================================
echo  THWS Antragsformular - Setup
echo ========================================
echo.
echo 1. Installiere Abhängigkeiten...
pip install -r requirements.txt
echo.
echo 2. Teste Ollama-Verbindung...
python ollama_chat.py
echo.
echo ========================================
echo Setup abgeschlossen!
echo.
echo Starten Sie die App mit:
echo    streamlit run app.py
echo.
echo ========================================
pause
