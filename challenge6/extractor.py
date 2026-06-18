import re
from typing import List, Dict, Any
from config import EXTRACTION_RULES, TARGET_SYSTEMS

try:
    from transformers import pipeline
    print("Loading local ML Model (Zero-Shot Classifier)... this might take a moment to download on first run.")
    # Using a smaller DistilBART model for prototype speed and local execution
    classifier = pipeline("zero-shot-classification", model="valhalla/distilbart-mnli-12-1")
    print("Loading local QA Model for detail extraction...")
    qa_extractor = pipeline("question-answering", model="deepset/minilm-uncased-squad2")
except ImportError:
    classifier = None
    qa_extractor = None
    print("Warning: 'transformers' or 'torch' not installed. Falling back to keyword rules.")

def extract_from_text(text: str, known_employees: List[str] = None, known_ifc_objects: List[str] = None) -> List[Dict[str, Any]]:
    """Extracts categories, persons, and IFC objects from text using simple matching rules."""
    extracted_items = []
    known_employees = known_employees or []
    known_ifc_objects = known_ifc_objects or []
    
    # Split text into manageable segments (roughly sentences) using newlines and common punctuation
    sentences = [s.strip() for s in re.split(r'[\n\.\?!]+', text) if s.strip()]
    
    for sentence in sentences:
        # Filter out short conversational filler and common email headers
        if len(sentence) < 15 or sentence.lower().startswith("subject:") or sentence.lower().startswith("hi") or sentence.lower().startswith("regards"):
            continue

        sentence_lower = sentence.lower()
        
        # Extract person (first one found)
        assigned_person = None
        for emp in known_employees:
            if emp.lower() in sentence_lower:
                assigned_person = emp
                break
                
        # Extract IFC object (first one found, case-sensitive)
        related_ifc_object = None
        for ifc in known_ifc_objects:
            if ifc in sentence:
                related_ifc_object = ifc
                break

        if classifier:
            # --- Machine Learning Approach ---
            categories = list(TARGET_SYSTEMS.keys())
            
            # Predict the most likely category based on sentence meaning
            result = classifier(sentence, categories)
            best_category = result["labels"][0]
            best_score = result["scores"][0]
            
            # Only extract if the model is somewhat confident
            if best_score > 0.25:
                actionable_detail = None
                if qa_extractor:
                    question = ""
                    if best_category == "Schedule": question = "What is the delay amount or schedule change?"
                    elif best_category == "Cost": question = "What is the cost or financial impact?"
                    elif best_category == "Quality": question = "What is the defect, blemish, or issue?"
                    elif best_category == "Task": question = "What is the task or action that needs to be done?"
                    elif best_category == "Open Point": question = "What is the open point or unresolved issue?"
                    
                    if question:
                        try:
                            ans = qa_extractor(question=question, context=sentence)
                            if ans['score'] > 0.05:
                                actionable_detail = ans['answer']
                        except Exception:
                            pass

                item = {
                    "extracted_text": sentence + ("." if not sentence.endswith('.') else ""),
                    "category": best_category,
                    "actionable_detail": actionable_detail,
                    "assigned_person": assigned_person,
                    "related_ifc_object": related_ifc_object,
                    "suggested_target_system": TARGET_SYSTEMS.get(best_category),
                    "confidence": round(best_score, 2)
                }
                extracted_items.append(item)
        else:
            # --- Fallback Rule-Based Approach ---
            for category, keywords in EXTRACTION_RULES.items():
                if any(keyword.lower() in sentence_lower for keyword in keywords):
                    
                    actionable_detail = None
                    if category == "Schedule":
                        m = re.search(r'(\d+\s*(?:working\s*)?(?:days|weeks|months|hrs|hours))', sentence_lower)
                        if m: actionable_detail = m.group(1)
                    elif category == "Cost":
                        m = re.search(r'(€\s*\d+(?:[.,]\d+)?|\d+(?:[.,]\d+)?\s*€)', sentence_lower)
                        if m: actionable_detail = m.group(1)

                    item = {
                        "extracted_text": sentence + ("." if not sentence.endswith('.') else ""),
                        "category": category,
                        "actionable_detail": actionable_detail,
                        "assigned_person": assigned_person,
                        "related_ifc_object": related_ifc_object,
                        "suggested_target_system": TARGET_SYSTEMS.get(category),
                        "confidence": 0.6
                    }
                    extracted_items.append(item)
                    break
                
    return extracted_items