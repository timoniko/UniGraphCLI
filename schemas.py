from utils import is_valid_date, valid_field


node_schemas = {
        "Student": [
            {"key": "matriculationNumber", "prompt": "What is student's matriculation number?",
             "validate": valid_field},
            {"key": "name", "prompt": "What is student's name?", "validate": valid_field}
        ],
        "Lecture": [
            {"key": "ects", "prompt": "What is lecture's ects count?", "validate": valid_field},
            {"key": "id", "prompt": "What is lecture's id?", "validate": valid_field},
            {"key": "topic", "prompt": "What is lecture's topic?", "validate": valid_field}
        ],
        "Professor": [
            {"key": "employeeNumber", "prompt": "What is professor's employee number?", "validate": valid_field},
            {"key": "name", "prompt": "What is professor's name?", "validate": valid_field}
        ],
        "Exam": [
            {"key": "date", "prompt": "What is exam's date?", "validate": is_valid_date},
            {"key": "note", "prompt": "Any note on exam?"},
            {"key": "room", "prompt": "What is exam's room?"}
        ]
    }
