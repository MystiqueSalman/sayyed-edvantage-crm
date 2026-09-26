"""
Sayyed EdVantage AI Agent — Master KB Batch 17
Unified 7-Course Retrieval

Purpose:
- One retrieval layer over the single Master KB architecture.
- Keeps every course isolated by course_id.
- Uses deterministic lexical retrieval with strong course-identity boosts.
- Preserves provenance/source IDs.
- Never enables execution, messaging, external actions, or CRM writes.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import re

# ---------------------------------------------------------------------------
# Source/course records
# ---------------------------------------------------------------------------

@dataclass
class SourceRecord:
    source_id: str
    title: str
    source_type: str
    version: str = "1.0"
    status: str = "approved"
    course_id: Optional[str] = None
    notes: str = ""

@dataclass
class CourseRecord:
    course_id: str
    official_name: str
    category: str
    status: str = "active"
    knowledge: Dict[str, Any] = field(default_factory=dict)
    source_ids: List[str] = field(default_factory=list)

@dataclass
class CommercialOffering:
    offering_id: str
    name: str
    offering_type: str
    pricing_regions: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    source_ids: List[str] = field(default_factory=list)

class MasterKnowledgeBase:
    def __init__(self):
        self.name = "Sayyed EdVantage Master Knowledge Base"
        self.version = "2.17"
        self.courses: Dict[str, CourseRecord] = {}
        self.offerings: Dict[str, CommercialOffering] = {}
        self.common_knowledge: Dict[str, Any] = {}
        self.sources: Dict[str, SourceRecord] = {}

    def register_source(self, source: SourceRecord) -> None:
        self.sources[source.source_id] = source

    def register_course(self, course: CourseRecord) -> None:
        self.courses[course.course_id] = course

    def register_offering(self, offering: CommercialOffering) -> None:
        self.offerings[offering.offering_id] = offering

    def get_course(self, course_id: str) -> Optional[CourseRecord]:
        return self.courses.get(course_id)

    def list_courses(self) -> List[CourseRecord]:
        return list(self.courses.values())

    def get_offering(self, offering_id: str) -> Optional[CommercialOffering]:
        return self.offerings.get(offering_id)

    def get_fee(self, offering_id: str, region: str = "india") -> Optional[Any]:
        offering = self.get_offering(offering_id)
        if not offering:
            return None
        region_data = offering.pricing_regions.get(region.lower())
        if not region_data:
            return None
        return region_data.get("base_fee")

    def set_common_knowledge(self, key: str, value: Any) -> None:
        self.common_knowledge[key] = value

    def get_common_knowledge(self, key: str, default: Any = None) -> Any:
        return self.common_knowledge.get(key, default)

    def validate(self) -> Dict[str, Any]:
        errors = []
        for cid, course in self.courses.items():
            if not cid or not course.official_name:
                errors.append(f"Invalid course record: {cid}")
            for sid in course.source_ids:
                if sid not in self.sources:
                    errors.append(f"{cid}: missing source {sid}")
        return {"valid": not errors, "errors": errors}

    def export_snapshot(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "courses": {k: vars(v) for k, v in self.courses.items()},
            "offerings": {k: vars(v) for k, v in self.offerings.items()},
            "common_knowledge": dict(self.common_knowledge),
            "sources": {k: vars(v) for k, v in self.sources.items()},
        }

# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

STOPWORDS = {
    "a","an","and","are","about","can","course","do","does","for","from",
    "give","how","i","in","is","it","me","of","on","or","please","the",
    "this","to","what","which","with","you"
}

COURSE_ALIASES = {
    "SE-DS-001": {
        "data", "science", "datascience", "ds",
        "machine", "learning", "ml", "python"
    },
    "SE-DA-001": {
        "data", "analytics", "dataanalytics", "da",
        "excel", "sql", "powerbi", "dax", "business", "analyst"
    },
    "SE-AIGEN-001": {
        "ai", "artificial", "intelligence", "generative", "genai",
        "llm", "llms", "langchain", "langgraph", "rag", "agentic"
    },
    "SE-PY-001": {
        "python", "programming", "code", "coding", "oop", "api", "automation"
    },
    "SE-LINUX-001": {
        "linux", "unix", "shell", "bash", "server", "systemd"
    },
    "SE-DEVOPS-001": {
        "devops", "docker", "kubernetes", "k8s", "terraform",
        "ansible", "jenkins", "cicd", "ci", "cd", "cloud"
    },
    "SE-EHC-001": {
        "ethical", "hacking", "cybersecurity", "cyber", "security",
        "pentesting", "pentest", "owasp", "soc", "ctf"
    },
}

def _tokens(text: str) -> List[str]:
    text = text.lower().replace("+", " plus ")
    raw = re.findall(r"[a-z0-9]+", text)
    return [t for t in raw if t not in STOPWORDS]

def _course_identity_tokens(course: CourseRecord) -> set:
    cid = course.course_id
    return set(COURSE_ALIASES.get(cid, set())) | set(_tokens(course.official_name))

def _flatten(value: Any, path: str = "") -> List[Dict[str, Any]]:
    """Create small retrieval records while retaining field/path provenance."""
    records: List[Dict[str, Any]] = []

    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            records.extend(_flatten(child, child_path))
    elif isinstance(value, list):
        for idx, child in enumerate(value):
            child_path = f"{path}[{idx}]"
            records.extend(_flatten(child, child_path))
    else:
        if value is not None:
            records.append({"path": path, "text": str(value)})
    return records

def _course_records(kb: MasterKnowledgeBase) -> List[Dict[str, Any]]:
    corpus = []
    for course in kb.list_courses():
        # Identity record is deliberately separate and gets the strongest
        # matching boost. This prevents generic terms such as "programming"
        # from outranking the course actually named by the user.
        corpus.append({
            "course_id": course.course_id,
            "official_name": course.official_name,
            "category": course.category,
            "path": "__course_identity__",
            "text": f"{course.official_name} {course.category}",
            "source_ids": list(course.source_ids),
            "course_status": course.status,
            "is_identity": True,
        })

        for item in _flatten(course.knowledge):
            corpus.append({
                "course_id": course.course_id,
                "official_name": course.official_name,
                "category": course.category,
                "path": item["path"],
                "text": item["text"],
                "source_ids": list(course.source_ids),
                "course_status": course.status,
                "is_identity": False,
            })
    return corpus

def _score_record(query: str, record: Dict[str, Any]) -> float:
    q = set(_tokens(query))
    if not q:
        return 0.0

    text_tokens = set(_tokens(record["text"]))
    overlap = len(q & text_tokens)

    # Strong exact course-name / alias detection.
    cid = record["course_id"]
    aliases = COURSE_ALIASES.get(cid, set())
    alias_hits = len(q & aliases)

    # Identity records should dominate when the user explicitly names a
    # course. This fixes ambiguous lexical matches such as:
    # "Python programming", "machine learning", and "Linux administration".
    identity_boost = 0.0
    if record.get("is_identity"):
        identity_boost = alias_hits * 100.0
        if query.lower().strip() == record["official_name"].lower().strip():
            identity_boost += 500.0

    # Course-level alias hits also provide a moderate boost to detail chunks.
    course_boost = alias_hits * 20.0

    # Phrase bonus for common course-name pairs.
    normalized = " ".join(_tokens(query))
    phrase_bonus = 0.0
    phrase_map = {
        "data science": "SE-DS-001",
        "data analytics": "SE-DA-001",
        "artificial intelligence": "SE-AIGEN-001",
        "generative ai": "SE-AIGEN-001",
        "ethical hacking": "SE-EHC-001",
        "cybersecurity": "SE-EHC-001",
        "machine learning": "SE-DS-001",
        "linux administration": "SE-LINUX-001",
        "devops": "SE-DEVOPS-001",
        "python programming": "SE-PY-001",
    }
    for phrase, target in phrase_map.items():
        if phrase in normalized and cid == target:
            phrase_bonus += 300.0

    return float(overlap + course_boost + identity_boost + phrase_bonus)

def retrieve(
    kb: MasterKnowledgeBase,
    query: str,
    top_k: int = 5,
    course_id: Optional[str] = None,
    category: Optional[str] = None,
) -> List[Dict[str, Any]]:
    if not query or not query.strip():
        return []

    corpus = _course_records(kb)

    if course_id:
        corpus = [r for r in corpus if r["course_id"] == course_id]
    if category:
        category_l = category.lower()
        corpus = [r for r in corpus if r["category"].lower() == category_l]

    scored = []
    for record in corpus:
        score = _score_record(query, record)
        if score > 0:
            result = dict(record)
            result["score"] = score
            result["provenance"] = {
                "course_id": record["course_id"],
                "source_ids": list(record["source_ids"]),
                "path": record["path"],
            }
            scored.append(result)

    # Deterministic ordering:
    # 1) score desc
    # 2) course identity before detail when tied
    # 3) course_id/path lexical tie-breakers
    scored.sort(
        key=lambda r: (
            -r["score"],
            0 if r.get("is_identity") else 1,
            r["course_id"],
            r["path"],
        )
    )
    return scored[:max(0, int(top_k))]

def retrieve_courses(
    kb: MasterKnowledgeBase,
    query: str,
    top_k: int = 5,
    category: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Return one best result per course, useful for course recommendation/ranking."""
    results = retrieve(kb, query, top_k=max(top_k * 3, 20), category=category)
    best: Dict[str, Dict[str, Any]] = {}
    for result in results:
        cid = result["course_id"]
        current = best.get(cid)
        if current is None or result["score"] > current["score"]:
            best[cid] = result

    output = list(best.values())
    output.sort(key=lambda r: (-r["score"], r["course_id"]))
    return output[:max(0, int(top_k))]

# Backward-compatible aliases
search_master_kb = retrieve
retrieve_from_master_kb = retrieve

# ---------------------------------------------------------------------------
# Master KB builder
# ---------------------------------------------------------------------------

def _course(
    course_id: str,
    official_name: str,
    category: str,
    knowledge: Dict[str, Any],
    source_id: str,
) -> CourseRecord:
    return CourseRecord(
        course_id=course_id,
        official_name=official_name,
        category=category,
        status="active",
        knowledge=knowledge,
        source_ids=[source_id],
    )

def build_master_kb_with_ehc() -> MasterKnowledgeBase:
    """Build the complete unified seven-course retrieval KB."""
    kb = MasterKnowledgeBase()

    common_source = SourceRecord(
        "COMMON-POLICY-001", "Master KB Common Policy",
        "policy", version="1.0", status="approved"
    )
    kb.register_source(common_source)

    course_data = [
        ("SE-DS-001", "Data Science", "Data Science", "CURRICULUM-DS-001", {
            "identity": "Data Science Professional Program",
            "duration": {"total_duration_hours": 60},
            "level": "Beginner to Intermediate",
            "delivery": "Online live",
            "goal": "Build practical data science skills.",
            "machine_learning": "Core data science area.",
            "tools": ["Python", "NumPy", "Pandas", "Matplotlib", "Seaborn", "Scikit-learn"],
            "boundaries": ["Advanced GenAI and agentic AI are outside the core Data Science program."],
        }),
        ("SE-DA-001", "Data Analytics", "Data Analytics", "CURRICULUM-DA-001", {
            "identity": "Data Analytics Professional Program",
            "duration": {"total_duration_hours": 60},
            "level": "Beginner to Intermediate",
            "tools": ["Excel", "Power Query", "SQL", "Power BI", "DAX"],
            "core": "Business analytics, data cleaning, SQL, statistics, visualization and BI.",
        }),
        ("SE-AIGEN-001", "AI + Generative AI – Professional Program",
         "Artificial Intelligence / Generative AI", "CURRICULUM-AIGEN-001", {
            "identity": "AI + Generative AI",
            "duration": {
                "declared_total_hours": 60,
                "module_hours_total": 59,
                "status": "documented_source_inconsistency",
            },
            "core": "AI, deep learning, NLP, transformers, generative AI, LLM applications, RAG and agentic AI.",
            "tools": ["LLMs", "LangChain", "LangGraph", "Vector Databases"],
        }),
        ("SE-PY-001", "Python", "Python Programming", "CURRICULUM-PY-001", {
            "identity": "Python Professional Program",
            "duration": {"total_duration_hours": 40},
            "level": "Beginner to Intermediate",
            "core": "Python programming, data structures, functions, OOP, APIs, automation and testing.",
            "tools": ["Python"],
        }),
        ("SE-LINUX-001", "Linux", "Linux Administration", "CURRICULUM-LINUX-001", {
            "identity": "Linux Administration Professional Program",
            "duration": {
                "declared_duration_hours": 40,
                "module_hours_total": 44,
                "status": "documented_source_inconsistency",
            },
            "core": "Linux administration, command line, filesystem, permissions, processes, networking, services and shell scripting.",
            "tools": ["Linux", "Bash", "systemd"],
        }),
        ("SE-DEVOPS-001", "DevOps", "DevOps", "CURRICULUM-DEVOPS-001", {
            "identity": "DevOps Professional Program",
            "duration": {"total_duration_hours": 60},
            "level": "Intermediate",
            "core": "CI/CD, Git, Docker, Kubernetes, Terraform, Ansible, cloud, monitoring and DevSecOps.",
            "tools": ["Git", "Jenkins", "Docker", "Kubernetes", "Terraform", "Ansible"],
        }),
        ("SE-EHC-001", "Ethical Hacking & Cybersecurity",
         "Cybersecurity", "CURRICULUM-EHC-001", {
            "identity": "Ethical Hacking & Cybersecurity – Professional Program",
            "duration": {"total_duration_hours": 60},
            "level": "Beginner to Intermediate to Advanced",
            "core": "Cybersecurity foundations, networking, OS security, reconnaissance, vulnerability assessment, web security, ethical penetration testing, SOC and incident response.",
            "safety": "Authorized labs, CTFs, VMs and explicitly permitted environments only.",
            "tools": ["Nmap", "Burp Suite", "Wireshark", "Metasploit", "Kali Linux"],
        }),
    ]

    for cid, name, category, sid, knowledge in course_data:
        kb.register_source(SourceRecord(
            sid, f"{name} Curriculum Source", "curriculum",
            version="1.0", status="approved", course_id=cid
        ))
        kb.register_course(_course(cid, name, category, knowledge, sid))

    kb.set_common_knowledge("india_pricing", "Quote only verified Indian pricing.")
    kb.set_common_knowledge("international_pricing", "Not currently defined; never substitute Indian pricing.")
    kb.set_common_knowledge("no_invention", True)
    kb.set_common_knowledge("provenance_required", True)
    kb.set_common_knowledge("execution_enabled", False)
    kb.set_common_knowledge("messaging_enabled", False)
    kb.set_common_knowledge("external_actions_enabled", False)
    kb.set_common_knowledge("crm_writes_enabled", False)

    return kb

# Names used by the Batch 17 test/integration layer.
build_master_kb_with_unified_retrieval = build_master_kb_with_ehc

def add_batch17_to_master_kb(kb: MasterKnowledgeBase) -> MasterKnowledgeBase:
    report = kb.validate()
    if not report["valid"]:
        raise ValueError(report["errors"])
    return kb

def build_master_kb_with_all_course_retrieval() -> MasterKnowledgeBase:
    return add_batch17_to_master_kb(build_master_kb_with_ehc())

if __name__ == "__main__":
    kb = build_master_kb_with_ehc()
    print("Batch 17 KB validation:", kb.validate())
    for q in ("Python programming", "machine learning", "Linux administration"):
        results = retrieve_courses(kb, q, top_k=3)
        print(q, "=>", [(r["course_id"], r["score"]) for r in results])
