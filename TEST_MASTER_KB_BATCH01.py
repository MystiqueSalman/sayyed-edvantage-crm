from Sayyed_EdVantage_Master_KB_BATCH01 import build_master_kb

kb = build_master_kb()
assert kb.name == "Sayyed EdVantage Master Knowledge Base"
assert kb.version == "1.0"
ds = kb.get_course("SE-DSP-001")
assert ds and ds.official_name == "Data Science – Professional Program"
assert kb.get_course("UNKNOWN") is None
india = kb.get_fee("SE-DSP-001", "india")
assert india["currency"] == "INR" and india["amount"] == 50000
intl = kb.get_fee("SE-DSP-001", "international")
assert intl["status"] == "unknown" and intl["amount"] is None and intl["currency"] is None
assert intl["amount"] != india["amount"]
policy = kb.get_common_knowledge("commercial_policy")
assert policy["no_invention"] is True
assert "Do not quote Indian pricing to international students" in policy["international_pricing"]
report = kb.validate()
assert report["valid"] and report["course_count"] == 1 and report["offering_count"] == 1
ds.knowledge["tampered"] = True
assert "tampered" not in kb.get_course("SE-DSP-001").knowledge
snapshot = kb.export_snapshot()
assert all(k in snapshot for k in ("courses", "offerings", "common_knowledge", "sources"))
print("MASTER KB BATCH 01: 10/10 PASSED")
