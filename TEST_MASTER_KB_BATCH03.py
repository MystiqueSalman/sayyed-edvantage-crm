from Sayyed_EdVantage_Master_KB_BATCH03 import *

r = validate_curriculum()
assert r["valid"] and r["module_count"] == 14 and r["total_hours"] == 60
assert get_data_science_module(1)["title"] == "Data Science Mindset & Real-World Problem Solving"
assert get_data_science_module(1)["hours"] == 3
assert "What is Data Science?" in get_data_science_module(1)["topic_details"]
assert get_data_science_module(3)["hours"] == 5
assert "INNER JOIN" in get_data_science_module(3)["topic_details"]
assert "Linear Regression" in get_data_science_module(9)["topic_details"]
assert "Random Forest" in get_data_science_module(9)["topic_details"]
assert "ROC-AUC" in get_data_science_module(9)["topic_details"]
assert "TF-IDF" in get_data_science_module(12)["topic_details"]
assert "MLflow fundamentals" in get_data_science_module(13)["topic_details"]
assert "Docker concepts" in get_data_science_module(13)["topic_details"]
assert get_data_science_module(99) is None
mods = get_all_data_science_modules()
assert len(mods) == 14 and sum(m["hours"] for m in mods) == 60
curr = get_data_science_curriculum()
assert curr["course_id"] == "SE-DSP-001"
assert curr["capstone"]["title"] == "End-to-End Data Science Project"
assert len(curr["capstone"]["workflow"]) == 11
kb = build_master_kb_with_curriculum()
course = kb.get_course("SE-DSP-001")
assert course.knowledge["detailed_curriculum"]["modules"][8]["title"] == "Supervised Machine Learning"
assert course.knowledge["detailed_curriculum"]["modules"][8]["hours"] == 7
assert course.source_ids == ["DS-CURRICULUM-SOURCE-001"]
assert kb.validate()["valid"]
course.knowledge["tampered"] = True
assert "tampered" not in kb.get_course("SE-DSP-001").knowledge
print("MASTER KB BATCH 03: 16/16 PASSED")
