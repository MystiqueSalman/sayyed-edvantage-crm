from copy import deepcopy
from typing import Any, Dict, List

DATA_SCIENCE_COURSE_ID = "SE-DSP-001"

PROJECTS = [
    {"name": "Python Data Processing System", "related_modules": [2], "type": "project"},
    {"name": "Business Data Investigation using SQL", "related_modules": [3], "type": "project"},
    {"name": "Messy Dataset / Data Quality Project", "related_modules": [4, 5], "type": "project"},
    {"name": "Exploratory Data Investigation", "related_modules": [6, 7], "type": "project"},
    {"name": "Predictive Machine Learning Project", "related_modules": [8, 9], "type": "project"},
    {"name": "Segmentation / Unsupervised Learning Project", "related_modules": [10], "type": "project"},
    {"name": "NLP Mini Project", "related_modules": [12], "type": "mini_project"},
    {"name": "Model Deployment Project", "related_modules": [13], "type": "project"},
    {"name": "End-to-End Data Science Project", "related_modules": list(range(1, 15)), "type": "final_capstone"},
]

ASSESSMENT = {
    "quizzes_and_assignments": {"percent": 15},
    "hands_on_labs": {"percent": 20},
    "mini_projects": {"percent": 20},
    "case_study_problem_solving": {"percent": 10},
    "capstone": {"percent": 25},
    "presentation_viva_technical_defense": {"percent": 10},
}

TOOLS = [
    "Python", "SQL", "NumPy", "Pandas", "Matplotlib", "Seaborn",
    "Scikit-Learn", "TensorFlow", "Keras", "Git", "GitHub", "MLflow",
    "Streamlit", "FastAPI", "Docker"
]

LEARNING_OUTCOMES = [
    "Understand and frame real-world problems using a Data Science workflow.",
    "Work with data collection, understanding, cleaning and quality processes.",
    "Use Python for Data Science programming and data processing.",
    "Extract and investigate data using SQL.",
    "Manipulate and analyze data using NumPy and Pandas.",
    "Perform exploratory data analysis and communicate patterns using visualization.",
    "Apply statistics and probability concepts relevant to Data Science.",
    "Build and evaluate supervised and unsupervised machine learning models.",
    "Apply feature engineering and model evaluation techniques.",
    "Understand foundations of deep learning and neural networks.",
    "Apply fundamental NLP techniques to text data.",
    "Understand basic MLOps and deployment practices using the listed tools.",
    "Develop, document, present and technically defend an end-to-end Data Science project."
]

MODULE_OUTCOME_MAP = {
    1: ["problem framing", "Data Science workflow", "analytical thinking"],
    2: ["Python programming", "data processing", "debugging"],
    3: ["SQL querying", "data extraction", "multi-table analysis"],
    4: ["NumPy arrays", "Pandas DataFrames", "data manipulation"],
    5: ["data quality", "data cleaning", "data preparation"],
    6: ["EDA", "data visualization", "analytical communication"],
    7: ["descriptive statistics", "probability", "hypothesis testing", "correlation vs causation"],
    8: ["machine learning foundations", "generalization", "overfitting and underfitting"],
    9: ["regression", "classification", "model evaluation", "model comparison"],
    10: ["clustering", "dimensionality reduction", "feature engineering"],
    11: ["neural network foundations", "training concepts", "TensorFlow/Keras foundations"],
    12: ["text preprocessing", "text representation", "basic NLP application"],
    13: ["model evaluation", "MLOps fundamentals", "deployment foundations"],
    14: ["portfolio development", "technical presentation", "technical defense"]
}

def get_project_knowledge() -> List[Dict[str, Any]]:
    return deepcopy(PROJECTS)

def get_assessment_knowledge() -> Dict[str, Any]:
    result = deepcopy(ASSESSMENT)
    result["total_percent"] = sum(v["percent"] for v in result.values())
    return result

def get_tools_knowledge() -> List[str]:
    return deepcopy(TOOLS)

def get_learning_outcomes() -> List[str]:
    return deepcopy(LEARNING_OUTCOMES)

def get_module_outcomes(module_number: int) -> List[str]:
    return deepcopy(MODULE_OUTCOME_MAP.get(module_number, []))

def validate_batch04() -> Dict[str, Any]:
    errors = []
    if len(PROJECTS) != 9:
        errors.append("Expected 9 project entries.")
    if sum(v["percent"] for v in ASSESSMENT.values()) != 100:
        errors.append("Assessment must total 100%.")
    if len(TOOLS) != 15:
        errors.append("Expected 15 tools from the supplied Data Science source.")
    if len(LEARNING_OUTCOMES) != 13:
        errors.append("Expected 13 learning outcomes.")
    if set(MODULE_OUTCOME_MAP) != set(range(1, 15)):
        errors.append("Learning outcomes must map to all 14 modules.")
    for project in PROJECTS:
        if not project["name"] or not project["related_modules"]:
            errors.append("Every project needs a name and module mapping.")
    return {
        "valid": not errors,
        "errors": errors,
        "project_count": len(PROJECTS),
        "assessment_total": sum(v["percent"] for v in ASSESSMENT.values()),
        "tool_count": len(TOOLS),
        "learning_outcome_count": len(LEARNING_OUTCOMES)
    }

def add_batch04_to_master_kb(kb):
    report = validate_batch04()
    if not report["valid"]:
        raise ValueError(report["errors"])
    course = kb.get_course(DATA_SCIENCE_COURSE_ID)
    if course is None:
        raise KeyError("Data Science course is missing from Master KB.")
    knowledge = deepcopy(course.knowledge)
    knowledge["project_knowledge"] = get_project_knowledge()
    knowledge["assessment_knowledge"] = get_assessment_knowledge()
    knowledge["tools_knowledge"] = get_tools_knowledge()
    knowledge["learning_outcomes"] = get_learning_outcomes()
    knowledge["module_outcomes"] = {
        n: get_module_outcomes(n) for n in range(1, 15)
    }
    course.knowledge = knowledge
    kb.register_course(course)
    return kb

def build_master_kb_with_batch04():
    from Sayyed_EdVantage_Master_KB_BATCH03 import build_master_kb_with_curriculum
    return add_batch04_to_master_kb(build_master_kb_with_curriculum())
