from copy import deepcopy
from typing import Any, Dict, List

DATA_SCIENCE_COURSE_ID = "SE-DSP-001"

ELIGIBILITY_KNOWLEDGE = {
    "course_id": DATA_SCIENCE_COURSE_ID,
    "level": "Beginner to Intermediate",
    "mode": "Instructor-Led / Online Live",
    "prerequisites": {
        "required": [
            "Basic computer knowledge",
            "Logical thinking"
        ],
        "programming_experience_required": False,
        "statement": "No prior programming experience required."
    },
    "suitable_for": [
        "Learners beginning their Data Science journey",
        "Learners who want practical Data Science skills",
        "Learners interested in working with data, statistics and machine learning",
        "Learners willing to practice problem solving, coding and projects"
    ],
    "not_specified_by_source": [
        "Minimum academic qualification",
        "Minimum age",
        "Work experience requirement",
        "English-language requirement",
        "Entrance examination requirement"
    ],
    "safety_rule": (
        "Fields not specified by the supplied curriculum must not be converted "
        "into mandatory eligibility requirements."
    )
}

CAREER_KNOWLEDGE = {
    "course_id": DATA_SCIENCE_COURSE_ID,
    "career_relevance": (
        "The program develops practical skills relevant to Data Science work, "
        "including Python, SQL, data preparation, statistics, visualization, "
        "machine learning, NLP, deployment and technical communication."
    ),
    "core_career_skills": [
        "Python programming",
        "SQL and data extraction",
        "Data cleaning and data quality",
        "Exploratory Data Analysis",
        "Statistics and probability",
        "Machine learning",
        "Feature engineering",
        "Model evaluation",
        "Basic deep learning",
        "NLP fundamentals",
        "MLOps and deployment foundations",
        "Project documentation and presentation"
    ],
    "career_preparation": [
        "GitHub portfolio development",
        "Project organization and README creation",
        "Resume project descriptions",
        "Technical interview preparation",
        "Data Science interview questions",
        "Explaining models and technical decisions",
        "Mock interview",
        "Technical presentation",
        "Viva / technical defense"
    ],
    "career_pathway": [
        "Build programming and data foundations",
        "Develop analytical and statistical capability",
        "Build machine learning capability",
        "Practice deployment and technical communication",
        "Build and present an end-to-end portfolio project"
    ],
    "supported_claims": [
        "The curriculum provides Data Science career preparation activities.",
        "The curriculum includes portfolio, interview and technical presentation preparation."
    ],
    "unsupported_claims": [
        "Guaranteed employment",
        "Guaranteed placement",
        "Guaranteed salary",
        "Guaranteed job title",
        "Guaranteed income"
    ],
    "safety_rule": (
        "Career relevance may be explained from curriculum skills, but the "
        "agent must not promise employment, placement, salary or income."
    )
}

BOUNDARY_KNOWLEDGE = {
    "course_id": DATA_SCIENCE_COURSE_ID,
    "data_science_scope": [
        "Data Science workflow",
        "Python for Data Science",
        "SQL and data extraction",
        "NumPy and Pandas",
        "Data cleaning and quality",
        "EDA and visualization",
        "Statistics and probability",
        "Machine learning",
        "Feature engineering",
        "Deep learning and neural networks",
        "NLP fundamentals",
        "Model evaluation",
        "MLOps and deployment foundations",
        "Projects and portfolio"
    ],
    "advanced_ai_topics_excluded": [
        "LangChain",
        "LangGraph",
        "RAG",
        "Agentic AI",
        "Advanced LLM application development",
        "LLMOps",
        "Advanced Generative AI"
    ],
    "boundary_statement": (
        "Advanced AI and Generative AI content belongs to the dedicated "
        "AI + Generative AI program."
    )
}

def get_eligibility_knowledge() -> Dict[str, Any]:
    return deepcopy(ELIGIBILITY_KNOWLEDGE)

def get_career_knowledge() -> Dict[str, Any]:
    return deepcopy(CAREER_KNOWLEDGE)

def get_boundary_knowledge() -> Dict[str, Any]:
    return deepcopy(BOUNDARY_KNOWLEDGE)

def validate_batch05() -> Dict[str, Any]:
    errors: List[str] = []

    if ELIGIBILITY_KNOWLEDGE["course_id"] != DATA_SCIENCE_COURSE_ID:
        errors.append("Eligibility course ID mismatch.")
    if "Basic computer knowledge" not in ELIGIBILITY_KNOWLEDGE["prerequisites"]["required"]:
        errors.append("Basic computer knowledge requirement missing.")
    if "Logical thinking" not in ELIGIBILITY_KNOWLEDGE["prerequisites"]["required"]:
        errors.append("Logical thinking requirement missing.")
    if ELIGIBILITY_KNOWLEDGE["prerequisites"]["programming_experience_required"] is not False:
        errors.append("Programming experience must not be required.")
    if len(ELIGIBILITY_KNOWLEDGE["not_specified_by_source"]) != 5:
        errors.append("Unexpected number of unspecified eligibility fields.")

    if CAREER_KNOWLEDGE["course_id"] != DATA_SCIENCE_COURSE_ID:
        errors.append("Career course ID mismatch.")
    if not CAREER_KNOWLEDGE["core_career_skills"]:
        errors.append("Career skills are empty.")
    if not CAREER_KNOWLEDGE["career_preparation"]:
        errors.append("Career preparation is empty.")
    if "Guaranteed employment" not in CAREER_KNOWLEDGE["unsupported_claims"]:
        errors.append("Employment guarantee protection missing.")
    if "Guaranteed salary" not in CAREER_KNOWLEDGE["unsupported_claims"]:
        errors.append("Salary guarantee protection missing.")

    if "LangChain" not in BOUNDARY_KNOWLEDGE["advanced_ai_topics_excluded"]:
        errors.append("LangChain boundary missing.")
    if "RAG" not in BOUNDARY_KNOWLEDGE["advanced_ai_topics_excluded"]:
        errors.append("RAG boundary missing.")
    if "Agentic AI" not in BOUNDARY_KNOWLEDGE["advanced_ai_topics_excluded"]:
        errors.append("Agentic AI boundary missing.")

    return {
        "valid": not errors,
        "errors": errors,
        "unspecified_eligibility_count": len(ELIGIBILITY_KNOWLEDGE["not_specified_by_source"]),
        "career_skill_count": len(CAREER_KNOWLEDGE["core_career_skills"]),
        "career_preparation_count": len(CAREER_KNOWLEDGE["career_preparation"]),
        "excluded_ai_topic_count": len(BOUNDARY_KNOWLEDGE["advanced_ai_topics_excluded"])
    }

def add_batch05_to_master_kb(kb):
    report = validate_batch05()
    if not report["valid"]:
        raise ValueError(report["errors"])

    course = kb.get_course(DATA_SCIENCE_COURSE_ID)
    if course is None:
        raise KeyError("Data Science course is missing from Master KB.")

    knowledge = deepcopy(course.knowledge)
    knowledge["eligibility_knowledge"] = get_eligibility_knowledge()
    knowledge["career_knowledge"] = get_career_knowledge()
    knowledge["boundary_knowledge"] = get_boundary_knowledge()
    course.knowledge = knowledge
    kb.register_course(course)
    return kb

def build_master_kb_with_batch05():
    from Sayyed_EdVantage_Master_KB_BATCH04 import build_master_kb_with_batch04
    return add_batch05_to_master_kb(build_master_kb_with_batch04())
