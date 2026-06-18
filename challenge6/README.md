# Green Tower Office Building Prototype

A simple Python AI prototype for analyzing and extracting information from synthetic construction documents.

## Folder Structure
```
project/
  data/
    green_tower_office_building_hackathon_dataset.json
  src/
    __init__.py
    config.py
    data_loader.py
    extractor.py
    evaluator.py
    main.py
  requirements.txt
  README.md
```

## How to Run

1. Ensure you have Python 3.8+ installed.
2. Make sure your dataset JSON is accessible (the config will default to the absolute path `/Users/pavinsp/Desktop/ConstructAI/green_tower_office_building_hackathon_dataset.json` if the `data/` folder is empty).
3. Navigate to the `project` root directory.
4. Run the main pipeline module:

```bash
python -m src.main
```