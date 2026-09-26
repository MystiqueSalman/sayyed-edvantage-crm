from Sayyed_EdVantage_Master_KB_BATCH04 import (
    PROJECTS, ASSESSMENT, TOOLS, LEARNING_OUTCOMES, MODULE_OUTCOME_MAP,
    get_project_knowledge, get_assessment_knowledge, get_tools_knowledge,
    get_learning_outcomes, get_module_outcomes, validate_batch04,
    build_master_kb_with_batch04
)

report = validate_batch04()
assert report["valid"] is True
assert len(PROJECTS) == 9
assert PROJECTS[0]["name"] == "Python Data Processing System"
assert PROJECTS[-1]["name"] == "End-to-End Data Science Project"
assert PROJECTS[-1]["type"] == "final_capstone"
assert PROJECTS[-1]["related_modules"] == list(range(1, 15))

assessment = get_assessment_knowledge()
assert assessment["total_percent"] == 100
assert assessment["quizzes_and_assignments"]["percent"] == 15
assert assessment["hands_on_labs"]["percent"] == 20
assert assessment["capstone"]["percent"] == 25
assert assessment["presentation_viva_technical_defense"]["percent"] == 10

tools = get_tools_knowledge()
assert len(tools) == 15
for tool in (
    "Python", "SQL", "Pandas", "Scikit-Learn", "TensorFlow", "Keras",
    "Git", "GitHub", "MLflow", "Streamlit", "FastAPI", "Docker"
):
    assert tool in tools

outcomes = get_learning_outcomes()
assert len(outcomes) == 13
assert any("real-world problems" in x for x in outcomes)
assert any("machine learning models" in x for x in outcomes)
assert any("end-to-end Data Science project" in x for x in outcomes)

assert set(MODULE_OUTCOME_MAP) == set(range(1, 15))
for n in range(1, 15):
    assert len(get_module_outcomes(n)) >= 1

assert "Python programming" in get_module_outcomes(2)
assert "SQL querying" in get_module_outcomes(3)
assert "regression" in get_module_outcomes(9)
assert "clustering" in get_module_outcomes(10)
assert "basic NLP application" in get_module_outcomes(12)
assert "deployment foundations" in get_module_outcomes(13)

assert get_module_outcomes(99) == []

projects = get_project_knowledge()
projects[0]["name"] = "TAMPERED"
assert PROJECTS[0]["name"] == "Python Data Processing System"

kb = build_master_kb_with_batch04()
course = kb.get_course("SE-DSP-001")
assert course is not None
assert len(course.knowledge["project_knowledge"]) == 9
assert course.knowledge["assessment_knowledge"]["total_percent"] == 100
assert len(course.knowledge["tools_knowledge"]) == 15
assert len(course.knowledge["learning_outcomes"]) == 13
assert len(course.knowledge["module_outcomes"]) == 14
assert course.knowledge["total_duration_hours"] == 60
assert len(course.knowledge["detailed_curriculum"]["modules"]) == 14
assert kb.validate()["valid"] is True

print("MASTER KB BATCH 04: 12/12 PASSED")
