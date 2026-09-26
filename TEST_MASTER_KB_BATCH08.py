from Sayyed_EdVantage_Master_KB_BATCH08 import (
    retrieve_from_master_kb, retrieve_data_science, retrieval_context,
    validate_batch08, build_master_kb_with_batch08
)

# 1. Validation
report = validate_batch08()
assert report["valid"] is True
assert report["corpus_count"] >= 10

# 2. Build integrated Master KB
kb = build_master_kb_with_batch08()
assert kb.validate()["valid"] is True

# 3. Module retrieval
results = retrieve_from_master_kb(kb, "Python programming for Data Science")
assert results
assert any(r["category"] == "module" and r["module_number"] == 2 for r in results)

# 4. SQL retrieval
results = retrieve_from_master_kb(kb, "SQL data extraction")
assert results
assert any(r["module_number"] == 3 for r in results if r["category"] == "module")

# 5. Machine learning retrieval
results = retrieve_from_master_kb(kb, "supervised machine learning regression classification")
assert results
assert any(r["module_number"] == 9 for r in results if r["category"] == "module")

# 6. Project retrieval
results = retrieve_from_master_kb(kb, "Predictive Machine Learning Project")
assert results
assert any(r["category"] == "project" for r in results)

# 7. Eligibility retrieval
results = retrieve_from_master_kb(kb, "prerequisites no prior programming experience")
assert results
assert any(r["category"] == "eligibility" for r in results)

# 8. Tools retrieval
results = retrieve_from_master_kb(kb, "Python Pandas Scikit Learn TensorFlow Docker")
assert results
assert any(r["category"] == "tools" for r in results)

# 9. Commercial retrieval
results = retrieve_from_master_kb(kb, "Data Science fee INR 50000")
assert results
assert any(r["category"] == "commercial" for r in results)

# 10. Category filter
results = retrieve_from_master_kb(kb, "Python SQL machine learning", category="module")
assert results
assert all(r["category"] == "module" for r in results)

# 11. No-match safety
assert retrieve_from_master_kb(kb, "zzzzxyqvunknownterm") == []
assert retrieve_from_master_kb(kb, "") == []

# 12. Provenance/course isolation
results = retrieve_from_master_kb(kb, "Python")
assert all(r["course_id"] == "SE-DSP-001" for r in results)
assert all("record_id" in r and "score" in r for r in results)

# 13. Context wrapper
ctx = retrieval_context(kb, "What is the Data Science duration?")
assert ctx["course_id"] == "SE-DSP-001"
assert ctx["matched"] is True
assert ctx["source_policy"]

# 14. Convenience retrieval
results = retrieve_data_science("Pandas data manipulation")
assert results
assert all(r["course_id"] == "SE-DSP-001" for r in results)

# 15. Retrieval metadata integrated
course = kb.get_course("SE-DSP-001")
meta = course.knowledge["retrieval_metadata"]
assert meta["enabled"] is True
assert meta["course_isolation"] is True
assert meta["provenance_required"] is True
assert meta["no_match_is_safe"] is True
assert meta["execution_allowed"] is False

# 16. Existing knowledge remains intact
assert course.knowledge["total_duration_hours"] == 60
assert len(course.knowledge["detailed_curriculum"]["modules"]) == 14
assert course.knowledge["commercial_knowledge"]["india"]["base_fee"] == 50000

print("MASTER KB BATCH 08: 16/16 PASSED")
