from copy import deepcopy
from typing import Any, Dict, List, Optional

DATA_SCIENCE_COURSE_ID = "SE-DSP-001"

def _build_corpus(kb) -> List[Dict[str, Any]]:
    course = kb.get_course(DATA_SCIENCE_COURSE_ID)
    if course is None:
        return []
    k = course.knowledge
    records = [
        {
            "record_id": "DS-OVERVIEW",
            "course_id": DATA_SCIENCE_COURSE_ID,
            "category": "overview",
            "title": k.get("official_name", "Data Science"),
            "text": " ".join([
                k.get("primary_goal", ""),
                k.get("prerequisites", ""),
                k.get("boundary_note", ""),
                k.get("differentiator", "")
            ])
        }
    ]
    for module in k.get("detailed_curriculum", {}).get("modules", []):
        records.append({
            "record_id": f"DS-MODULE-{module['number']:02d}",
            "course_id": DATA_SCIENCE_COURSE_ID,
            "category": "module",
            "module_number": module["number"],
            "title": module["title"],
            "text": " ".join(module.get("topic_groups", [])) + " " + module.get("practical", "")
        })
    for project in k.get("project_knowledge", []):
        records.append({
            "record_id": "DS-PROJECT-" + project["name"].upper().replace(" ", "-").replace("/", "-"),
            "course_id": DATA_SCIENCE_COURSE_ID,
            "category": "project",
            "title": project["name"],
            "text": project["name"] + " " + " ".join(map(str, project.get("related_modules", [])))
        })
    records.append({
        "record_id": "DS-ASSESSMENT",
        "course_id": DATA_SCIENCE_COURSE_ID,
        "category": "assessment",
        "title": "Data Science Assessment",
        "text": " ".join(k.get("assessment_knowledge", {}).keys())
    })
    records.append({
        "record_id": "DS-TOOLS",
        "course_id": DATA_SCIENCE_COURSE_ID,
        "category": "tools",
        "title": "Data Science Tools",
        "text": " ".join(k.get("tools_knowledge", []))
    })
    records.append({
        "record_id": "DS-ELIGIBILITY",
        "course_id": DATA_SCIENCE_COURSE_ID,
        "category": "eligibility",
        "title": "Data Science Eligibility",
        "text": k.get("eligibility_knowledge", {}).get("prerequisites", {}).get("statement", "")
    })
    records.append({
        "record_id": "DS-CAREER",
        "course_id": DATA_SCIENCE_COURSE_ID,
        "category": "career",
        "title": "Data Science Career Knowledge",
        "text": " ".join(k.get("career_knowledge", {}).get("core_career_skills", []))
    })
    records.append({
        "record_id": "DS-COMMERCIAL",
        "course_id": DATA_SCIENCE_COURSE_ID,
        "category": "commercial",
        "title": "Data Science Commercial Knowledge",
        "text": " ".join([
            str(k.get("commercial_knowledge", {}).get("india", {}).get("base_fee", "")),
            str(k.get("commercial_knowledge", {}).get("india", {}).get("currency", "")),
            k.get("commercial_knowledge", {}).get("international", {}).get("notes", "")
        ])
    })
    return records

def _tokens(text: str) -> List[str]:
    cleaned = "".join(ch.lower() if ch.isalnum() else " " for ch in str(text))
    return [x for x in cleaned.split() if len(x) > 1]

def retrieve_from_master_kb(kb, query: str, top_k: int = 5,
                            category: Optional[str] = None) -> List[Dict[str, Any]]:
    if not query or not query.strip():
        return []
    q = set(_tokens(query))
    scored = []
    for record in _build_corpus(kb):
        if category and record["category"] != category:
            continue
        text_tokens = set(_tokens(record["title"] + " " + record["text"]))
        score = len(q & text_tokens)
        if score:
            item = deepcopy(record)
            item["score"] = score
            item["course_id"] = DATA_SCIENCE_COURSE_ID
            scored.append(item)
    scored.sort(key=lambda r: (-r["score"], r["record_id"]))
    return scored[:max(1, top_k)]

def retrieve_data_science(query: str, top_k: int = 5,
                          category: Optional[str] = None) -> List[Dict[str, Any]]:
    from Sayyed_EdVantage_Master_KB_BATCH07 import build_master_kb_with_batch07
    return retrieve_from_master_kb(build_master_kb_with_batch07(), query, top_k, category)

def retrieval_context(kb, query: str, top_k: int = 5) -> Dict[str, Any]:
    results = retrieve_from_master_kb(kb, query, top_k)
    return {
        "query": query,
        "course_id": DATA_SCIENCE_COURSE_ID,
        "matched": bool(results),
        "results": results,
        "source_policy": "Use retrieved records only; do not invent unsupported facts."
    }

def validate_batch08() -> Dict[str, Any]:
    errors = []
    from Sayyed_EdVantage_Master_KB_BATCH07 import build_master_kb_with_batch07
    kb = build_master_kb_with_batch07()
    corpus = _build_corpus(kb)
    if not corpus:
        errors.append("Retrieval corpus is empty.")
    if not any(r["category"] == "module" for r in corpus):
        errors.append("Module records missing.")
    if not any(r["category"] == "commercial" for r in corpus):
        errors.append("Commercial record missing.")
    if not any(r["category"] == "eligibility" for r in corpus):
        errors.append("Eligibility record missing.")
    return {"valid": not errors, "errors": errors, "corpus_count": len(corpus)}

def add_batch08_to_master_kb(kb):
    report = validate_batch08()
    if not report["valid"]:
        raise ValueError(report["errors"])
    course = kb.get_course(DATA_SCIENCE_COURSE_ID)
    knowledge = deepcopy(course.knowledge)
    knowledge["retrieval_metadata"] = {
        "enabled": True,
        "course_isolation": True,
        "provenance_required": True,
        "no_match_is_safe": True,
        "execution_allowed": False
    }
    course.knowledge = knowledge
    kb.register_course(course)
    return kb

def build_master_kb_with_batch08():
    from Sayyed_EdVantage_Master_KB_BATCH07 import build_master_kb_with_batch07
    return add_batch08_to_master_kb(build_master_kb_with_batch07())
