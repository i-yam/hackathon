import json
from config import DATA_FILE
from data_loader import load_dataset
from extractor import extract_from_text
from evaluator import evaluate_extractions

def main() -> None:
    print("Loading dataset...")
    dataset = load_dataset(DATA_FILE)
    documents = dataset.get("documents", [])
    
    if not documents:
        return

    # Extract known entities to pass into our extractor
    employees = list(dataset.get("employee_directory", {}).values())
    ifc_objects = []
    for category_list in dataset.get("ifc_objects", {}).values():
        ifc_objects.extend(category_list)

    print(f"Successfully loaded {len(documents)} documents.")
    
    all_predicted = []
    total_extracted = 0
    
    print("\nRunning rule-based extraction pipeline with entity matching...")
    for doc in documents:
        text = doc.get("DOCUMENT_TEXT", "")
        extracted = extract_from_text(text, known_employees=employees, known_ifc_objects=ifc_objects)
        all_predicted.append(extracted)
        total_extracted += len(extracted)

    print(f"Total extractions found: {total_extracted}")
    evaluate_extractions(documents, all_predicted)
    
    print("\n--- Sample Predictions (First Document) ---")
    print(json.dumps(all_predicted[0], indent=2))

if __name__ == "__main__":
    main()