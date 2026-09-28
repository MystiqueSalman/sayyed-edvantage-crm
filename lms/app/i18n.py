"""Phase 12 §21.3 — lightweight multi-language foundation (EN + Hindi).

A JSON-dictionary approach (no Flask-Babel dependency): UI strings live in
STRINGS, the active language is stored in the session ("lang"), and
templates call t("courses"). Extensible: add a language by adding a
dict and listing it in LANGUAGES.

Only key visitor-facing strings are translated (nav, hero, buttons,
footer) — the pattern covers the rest of the app later without rewrites.
"""
from flask import has_request_context, session

LANGUAGES = (
    ("en", "EN"),
    ("hi", "हिं"),
)

STRINGS = {
    "en": {
        "courses": "Courses",
        "jobs": "Jobs",
        "enquire": "Enquire",
        "login": "Login",
        "logout": "Logout",
        "dashboard": "Dashboard",
        "hero_kicker": "Admissions Open · Live Online Classes",
        "hero_title": "Master the Skills That Get You Hired.",
        "hero_sub": ("Data Science, AI & Generative AI, Python, Data Analytics, "
                     "Linux, DevOps and Ethical Hacking — taught live by industry "
                     "mentors, with recordings, quizzes, assignments and certificates."),
        "explore_courses": "Explore Courses",
        "tagline": "Empowering Students for Success",
        "location": "Mumbai, India",
    },
    "hi": {
        "courses": "पाठ्यक्रम",
        "jobs": "नौकरियां",
        "enquire": "पूछताछ",
        "login": "लॉगिन",
        "logout": "लॉगआउट",
        "dashboard": "डैशबोर्ड",
        "hero_kicker": "प्रवेश खुले हैं · लाइव ऑनलाइन कक्षाएं",
        "hero_title": "वो स्किल्स सीखें जिनसे नौकरी मिले।",
        "hero_sub": ("डेटा साइंस, AI और जेनरेटिव AI, पाइथन, डेटा एनालिटिक्स, "
                     "लिनक्स, डेवऑप्स और एथिकल हैकिंग — इंडस्ट्री मेंटर्स द्वारा "
                     "लाइव पढ़ाया जाता है, रिकॉर्डिंग, क्विज़, असाइनमेंट और "
                     "सर्टिफिकेट के साथ।"),
        "explore_courses": "कोर्स देखें",
        "tagline": "छात्रों की सफलता के लिए सशक्तिकरण",
        "location": "मुंबई, भारत",
    },
}


def get_lang():
    """Active language code ('en' default). Safe outside requests too."""
    if has_request_context():
        code = session.get("lang", "en")
        if code in STRINGS:
            return code
    return "en"


def set_lang(code):
    """Persist the visitor's language choice in the session."""
    if code in STRINGS:
        session["lang"] = code
        return True
    return False


def t(key):
    """Translate a UI string key; falls back to English, then the key."""
    lang = get_lang()
    return STRINGS.get(lang, {}).get(key) or STRINGS["en"].get(key, key)
