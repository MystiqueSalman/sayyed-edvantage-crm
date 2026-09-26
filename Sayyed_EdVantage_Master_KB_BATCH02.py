from copy import deepcopy
from typing import Any, Dict, List

DATA_SCIENCE_SOURCE_ID = "DS-CURRICULUM-SOURCE-001"
DATA_SCIENCE_COURSE_ID = "SE-DSP-001"

DATA_SCIENCE_KNOWLEDGE = {
    "course_id": DATA_SCIENCE_COURSE_ID,
    "official_name": "Data Science – Professional Program",
    "course_category": "Data Science",
    "course_status": "Current Professional Program Curriculum",
    "total_duration_hours": 60,
    "level": "Beginner to Intermediate",
    "mode": "Instructor-Led / Online Live",
    "prerequisites": "Basic computer knowledge and logical thinking. No prior programming experience required.",
    "primary_goal": "Teach students to understand, analyze, model and solve real-world problems using the complete Data Science workflow.",
    "core_learning_flow": [
        "Problem Definition", "Data Understanding", "Data Collection",
        "Data Cleaning", "Exploratory Data Analysis", "Statistics",
        "Feature Engineering", "Machine Learning", "Model Evaluation",
        "Deployment", "Communication"
    ],
    "teaching_philosophy": [
        "Practical implementation", "Real-world datasets", "Problem solving",
        "Debugging", "Projects",
        "Technical explanation rather than only theory/memorization"
    ],
    "modules": [
        {"number": 1, "title": "Data Science Mindset & Real-World Problem Solving", "hours": 3},
        {"number": 2, "title": "Python Programming for Data Science", "hours": 7},
        {"number": 3, "title": "SQL & Data Extraction", "hours": 5},
        {"number": 4, "title": "NumPy & Pandas", "hours": 6},
        {"number": 5, "title": "Data Cleaning & Data Quality", "hours": 5},
        {"number": 6, "title": "EDA & Data Visualization", "hours": 5},
        {"number": 7, "title": "Statistics & Probability for Data Science", "hours": 5},
        {"number": 8, "title": "Machine Learning Foundations", "hours": 3},
        {"number": 9, "title": "Supervised Machine Learning", "hours": 7},
        {"number": 10, "title": "Unsupervised Learning & Feature Engineering", "hours": 4},
        {"number": 11, "title": "Deep Learning & Neural Networks", "hours": 3},
        {"number": 12, "title": "NLP Fundamentals", "hours": 2},
        {"number": 13, "title": "Model Evaluation, MLOps & Deployment", "hours": 3},
        {"number": 14, "title": "Projects, Portfolio & Data Science Career Lab", "hours": 2},
    ],
    "projects": [
        "Python Data Processing System",
        "Business Data Investigation using SQL",
        "Messy Dataset / Data Quality Project",
        "Exploratory Data Investigation",
        "Predictive Machine Learning Project",
        "Segmentation / Unsupervised Learning Project",
        "NLP Mini Project",
        "Model Deployment Project",
        "End-to-End Data Science Project (Final Capstone)",
    ],
    "assessment": {
        "quizzes_and_assignments_percent": 15,
        "hands_on_labs_percent": 20,
        "mini_projects_percent": 20,
        "case_study_problem_solving_percent": 10,
        "capstone_percent": 25,
        "presentation_viva_technical_defense_percent": 10,
    },
    "tools": [
        "Python", "SQL", "NumPy", "Pandas", "Matplotlib", "Seaborn",
        "Scikit-Learn", "TensorFlow", "Keras", "Git", "GitHub", "MLflow",
        "Streamlit", "FastAPI", "Docker"
    ],
    "course_boundary_excluded": [
        "LangChain", "LangGraph", "RAG", "Agentic AI",
        "Advanced LLM application development", "LLMOps",
        "Advanced Generative AI"
    ],
    "boundary_note": "These advanced AI and Generative AI topics belong to the dedicated AI + Generative AI program.",
    "differentiator": "Teach when, why and how to use algorithms, evaluate them, and when not to use them.",
    "project_implementation_note": "Additional hands-on project work is distributed through Modules 2–13; project implementation is integrated into technical modules.",
    "capstone": {
        "title": "End-to-End Data Science Project",
        "workflow": [
            "Problem Definition", "Data Understanding", "Data Collection",
            "Data Cleaning", "EDA", "Statistics", "Feature Engineering",
            "Machine Learning", "Model Evaluation", "Deployment", "Communication"
        ]
    },
    "unsupported_or_unspecified": {
        "fee_details_in_curriculum": "Not specified in the curriculum source.",
        "certification_details_in_curriculum": "Not specified in the curriculum source.",
        "placement_guarantee": "Not supported.",
        "salary_guarantee": "Not supported."
    }
}

def validate_data_science_knowledge() -> Dict[str, Any]:
    errors: List[str] = []
    if DATA_SCIENCE_KNOWLEDGE["course_id"] != DATA_SCIENCE_COURSE_ID:
        errors.append("Course ID mismatch.")
    if len(DATA_SCIENCE_KNOWLEDGE["modules"]) != 14:
        errors.append("Data Science must contain exactly 14 modules.")
    total = sum(m["hours"] for m in DATA_SCIENCE_KNOWLEDGE["modules"])
    if total != 60:
        errors.append(f"Module hours total is {total}, expected 60.")
    assessment_total = sum(DATA_SCIENCE_KNOWLEDGE["assessment"].values())
    if assessment_total != 100:
        errors.append(f"Assessment total is {assessment_total}, expected 100.")
    if not DATA_SCIENCE_KNOWLEDGE["projects"]:
        errors.append("Project list is empty.")
    if "Advanced Generative AI" not in DATA_SCIENCE_KNOWLEDGE["course_boundary_excluded"]:
        errors.append("Advanced Generative AI boundary missing.")
    return {
        "valid": not errors, "errors": errors,
        "course_id": DATA_SCIENCE_COURSE_ID,
        "module_count": len(DATA_SCIENCE_KNOWLEDGE["modules"]),
        "module_hours": total,
        "assessment_total": assessment_total,
        "project_count": len(DATA_SCIENCE_KNOWLEDGE["projects"])
    }

def add_data_science_to_master_kb(kb):
    validation = validate_data_science_knowledge()
    if not validation["valid"]:
        raise ValueError(validation["errors"])
    course = kb.get_course(DATA_SCIENCE_COURSE_ID)
    if course is None:
        raise KeyError("Data Science course record is missing from the Master KB.")
    course.knowledge = deepcopy(DATA_SCIENCE_KNOWLEDGE)
    course.source_ids = [DATA_SCIENCE_SOURCE_ID]
    from Sayyed_EdVantage_Master_KB_BATCH01 import SourceRecord
    kb.register_source(SourceRecord(
        source_id=DATA_SCIENCE_SOURCE_ID,
        title="Data Science – Professional Program Curriculum",
        source_type="official_course_curriculum",
        version="1.0",
        status="approved",
        course_id=DATA_SCIENCE_COURSE_ID,
        notes="Authoritative supplied curriculum source for Data Science."
    ))
    kb.register_course(course)
    return kb

def build_master_kb_with_data_science():
    from Sayyed_EdVantage_Master_KB_BATCH01 import build_master_kb
    return add_data_science_to_master_kb(build_master_kb())
