import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from Sayyed_EdVantage_Master_KB_BATCH17 import (
    build_master_kb_with_all_course_retrieval,
    build_master_kb_with_unified_retrieval,
    retrieve,
    retrieve_courses,
)

passed = 0
total = 0

def check(condition, label):
    global passed, total
    total += 1
    if not condition:
        raise AssertionError(label)
    passed += 1

kb = build_master_kb_with_all_course_retrieval()

# 1–3: seven isolated course records
check(len(kb.courses) == 7, "Expected 7 course records")
check(set(kb.courses) == {
    "SE-DS-001","SE-DA-001","SE-AIGEN-001","SE-PY-001",
    "SE-LINUX-001","SE-DEVOPS-001","SE-EHC-001"
}, "Unexpected course IDs")
check(all(c.status == "active" for c in kb.courses.values()), "All courses must be active")

# 4–6: retrieval and isolation
r = retrieve(kb, "Python programming", top_k=5)
check(r, "Python retrieval returned no results")
check(r[0]["course_id"] == "SE-PY-001", "Python programming should rank the Python course first")
r2 = retrieve(kb, "machine learning", top_k=5)
check(r2 and r2[0]["course_id"] == "SE-DS-001", "Machine learning should rank Data Science first")

# 7–9: Linux identity and filters
r3 = retrieve(kb, "Linux administration", top_k=5)
check(r3 and r3[0]["course_id"] == "SE-LINUX-001", "Linux administration should rank Linux first")
filtered = retrieve(kb, "Docker Kubernetes", top_k=5, course_id="SE-DEVOPS-001")
check(filtered and all(x["course_id"] == "SE-DEVOPS-001" for x in filtered), "Course filter isolation failed")
wrong_filtered = retrieve(kb, "Docker Kubernetes", top_k=5, course_id="SE-PY-001")
check(wrong_filtered == [], "Course filter should safely return no match")

# 10–12: provenance
p = retrieve(kb, "Power BI", top_k=3)
check(p, "Power BI retrieval failed")
check("provenance" in p[0], "Provenance missing")
check(p[0]["provenance"]["course_id"] == p[0]["course_id"], "Provenance course mismatch")

# 13–15: safe no-match and deterministic behavior
check(retrieve(kb, "zzzz nonexistent topic", top_k=5) == [], "No-match should be safe")
a = retrieve(kb, "Python programming", top_k=5)
b = retrieve(kb, "Python programming", top_k=5)
check([(x["course_id"], x["path"], x["score"]) for x in a] ==
      [(x["course_id"], x["path"], x["score"]) for x in b], "Retrieval is not deterministic")
check(retrieve(kb, "", top_k=5) == [], "Empty query should return no results")

# 16–18: safety/common architecture
check(kb.get_common_knowledge("no_invention") is True, "No-invention policy missing")
check(kb.get_common_knowledge("provenance_required") is True, "Provenance policy missing")
check(kb.get_common_knowledge("execution_enabled") is False, "Execution must remain disabled")

# Builder alias regression
kb2 = build_master_kb_with_unified_retrieval()
check(len(kb2.courses) == 7, "Unified builder regression failed")

print(f"MASTER KB BATCH 17: {passed}/{total} PASSED")
