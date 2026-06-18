import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Provide fallback to the specific absolute path provided in the workspace
DATA_FILE = os.path.join(BASE_DIR, "data", "green_tower_office_building_hackathon_dataset.json")
if not os.path.exists(DATA_FILE):
    DATA_FILE = "/Users/pavinsp/Desktop/ConstructAI/green_tower_office_building_hackathon_dataset.json"

EXTRACTION_RULES = {
    "Schedule": ["delayed", "slipped", "moved", "revised slot", "follow-up inspection date"],
    "Cost": ["claim", "surcharge", "overtime cost", "budget", "add roughly €"],
    "Quality": ["noted a", "crack", "misaligned", "blemish", "surface issue", "finish requirement", "re-inspection"],
    "Task": ["should", "must arrange", "needs to close", "coordinate", "update"],
    "Responsibility": ["responsible", "assigned", "keep responsibility"],
    "Decision": ["approved", "confirmed", "agreed", "can be used"],
    "Open Point": ["open point"]
}

TARGET_SYSTEMS = {
    "Schedule": "Schedule Board",
    "Cost": "Cost Control",
    "Quality": "QA/QC Log",
    "Task": "Task Management",
    "Responsibility": "Responsibility Matrix",
    "Decision": "Decision Register",
    "Open Point": "Issue Log"
}

EMPLOYEE_PHONE_NUMBERS = {
    "Michael Schmidt": "+491623828298",
    "Sarah Weber": "+1234567891",
    "John Miller": "+1234567892",
    "Anna Keller": "+1234567893",
    "David Braun": "+1234567894",
    "Markus Fischer": "+1234567895"
}

# Twilio Automated WhatsApp Credentials
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_WHATSAPP_NUMBER = os.environ.get("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")