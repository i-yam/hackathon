"""
Test-Skript um die Bedingungslogik zu testen
"""

# Simuliere die Bedingung aus der data.json
test_cases = [
    {
        "name": "Neueinstellung Feld sollte erscheinen",
        "form_data": {
            "antrag.typ": "einstellung"
        },
        "condition": {
            "field": "antrag.typ",
            "op": "=",
            "value": "einstellung"
        },
        "expected": True
    },
    {
        "name": "Neueinstellung Feld sollte NICHT erscheinen",
        "form_data": {
            "antrag.typ": "weiterbeschaeftigung"
        },
        "condition": {
            "field": "antrag.typ",
            "op": "=",
            "value": "einstellung"
        },
        "expected": False
    },
    {
        "name": "Frühere Beschäftigung Details sollte erscheinen",
        "form_data": {
            "antrag.typ": "einstellung",
            "person.neueinstellung.fruehereBeschaeftigung.vorhanden": "ja"
        },
        "condition": {
            "allOf": [
                {"field": "antrag.typ", "op": "=", "value": "einstellung"},
                {"field": "person.neueinstellung.fruehereBeschaeftigung.vorhanden", "op": "=", "value": "ja"}
            ]
        },
        "expected": True
    },
    {
        "name": "Frühere Beschäftigung Details sollte NICHT erscheinen (nein gewählt)",
        "form_data": {
            "antrag.typ": "einstellung",
            "person.neueinstellung.fruehereBeschaeftigung.vorhanden": "nein"
        },
        "condition": {
            "allOf": [
                {"field": "antrag.typ", "op": "=", "value": "einstellung"},
                {"field": "person.neueinstellung.fruehereBeschaeftigung.vorhanden", "op": "=", "value": "ja"}
            ]
        },
        "expected": False
    }
]

def evaluate_condition(condition, form_data):
    """Simuliert die evaluate_condition Methode"""
    if not condition:
        return True
    
    if 'field' in condition:
        field_value = form_data.get(condition['field'])
        op = condition.get('op', '=')
        target = condition.get('value')
        
        if op == '=':
            return field_value == target
        elif op == '!=':
            return field_value != target
        elif op == 'blank':
            return not field_value
        elif op == '!blank':
            return bool(field_value)
    
    if 'anyOf' in condition:
        return any(evaluate_condition(c, form_data) for c in condition['anyOf'])
    
    if 'allOf' in condition:
        return all(evaluate_condition(c, form_data) for c in condition['allOf'])
    
    return True

# Tests ausführen
print("=" * 60)
print("BEDINGUNGSLOGIK TEST")
print("=" * 60)

for test in test_cases:
    result = evaluate_condition(test['condition'], test['form_data'])
    status = "✅ PASS" if result == test['expected'] else "❌ FAIL"
    print(f"\n{status} - {test['name']}")
    print(f"   Form Data: {test['form_data']}")
    print(f"   Expected: {test['expected']}, Got: {result}")

print("\n" + "=" * 60)
print("Test abgeschlossen!")
print("=" * 60)
