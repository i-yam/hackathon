from typing import List, Dict, Any

def evaluate_extractions(documents: List[Dict[str, Any]], all_predicted: List[List[Dict[str, Any]]]) -> None:
    """Compares predicted categories and entities with expected items and prints simple metrics."""
    total_expected = 0
    correct_categories = 0
    correct_persons = 0
    correct_ifc = 0
    category_stats: Dict[str, Dict[str, int]] = {}

    for doc, predicted_items in zip(documents, all_predicted):
        expected_items = doc.get("EXPECTED_EXTRACTIONS", [])
        
        for expected_item in expected_items:
            expected_cat = expected_item["category"]
            expected_person = expected_item.get("assigned_person")
            expected_ifc = expected_item.get("related_ifc_object")
            
            total_expected += 1
            if expected_cat not in category_stats:
                category_stats[expected_cat] = {"total": 0, "correct": 0}
            
            category_stats[expected_cat]["total"] += 1
            
            # Find a matching predicted item by category
            predicted_match = next((p for p in predicted_items if p["category"] == expected_cat), None)
            
            if predicted_match:
                correct_categories += 1
                category_stats[expected_cat]["correct"] += 1
                
                if predicted_match.get("assigned_person") == expected_person:
                    correct_persons += 1
                if predicted_match.get("related_ifc_object") == expected_ifc:
                    correct_ifc += 1

    print("\n--- Evaluation Summary (Recall) ---")
    print(f"Category Match:      {correct_categories}/{total_expected} ({(correct_categories/total_expected*100) if total_expected else 0:.2f}%)")
    print(f"Assigned Person:     {correct_persons}/{total_expected} ({(correct_persons/total_expected*100) if total_expected else 0:.2f}%)")
    print(f"Related IFC Object:  {correct_ifc}/{total_expected} ({(correct_ifc/total_expected*100) if total_expected else 0:.2f}%)")

    print("\nCategory-level Accuracy:")
    for cat, stats in category_stats.items():
        acc = (stats["correct"] / stats["total"] * 100) if stats["total"] > 0 else 0.0
        print(f"  - {cat:15}: {acc:6.2f}% ({stats['correct']}/{stats['total']})")