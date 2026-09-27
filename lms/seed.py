"""Seed the LMS with demo users, 7 courses + 2 bonus courses, and content.
Idempotent: safe to re-run (skips existing rows).
"""
from datetime import date, datetime, timedelta

from app import create_app, db
from app.models import (Announcement, Assignment, Course, Coupon, Lesson, LiveSession,
                        Module, Question, Quiz, Recording, User)

app = create_app()

COURSES = [
    {
        "title": "Data Science", "slug": "data-science", "fee": 50000,
        "banner": "data-science.png",
        "short": "Master Python, statistics, machine learning and real-world DS projects.",
        "desc": "<p>Become a job-ready <b>Data Scientist</b>: Python, statistics, data wrangling with Pandas, visualization, and machine learning with Scikit-Learn — taught through live classes and hands-on projects.</p>",
        "modules": [
            ("Python & Statistics Foundations", [
                ("Welcome to Data Science", "text",
                 "<p>What data science is, how the industry hires, and your roadmap for the next 12 weeks.</p>"),
                ("Python for Data Analysis (Live Demo)", "video", ""),
                ("Statistics Cheat Sheet", "text",
                 "<p>Mean, median, mode, variance, distributions and hypothesis testing — the only stats a data scientist uses daily.</p>"),
            ]),
            ("Machine Learning Essentials", [
                ("ML Concepts: Regression & Classification", "text",
                 "<p>Supervised vs unsupervised learning, training/test splits, and how to pick the right algorithm.</p>"),
                ("Build Your First Model (Live Demo)", "video", ""),
                ("Capstone Project Guide", "text",
                 "<p>End-to-end project: collect data, clean it, train a model, and present insights like a pro.</p>"),
            ]),
        ],
        "quiz": [
            ("Module 1 Quiz", [
                ("Which library is used for data manipulation in Python?",
                 ["NumPy", "Pandas", "Matplotlib", "Requests"], "B"),
                ("Median is preferred over mean when the data has…",
                 ["No missing values", "Outliers", "Text columns", "Duplicates"], "B"),
            ]),
            ("Module 2 Quiz", [
                ("Splitting data into train and test sets helps to…",
                 ["Speed up training", "Measure generalization", "Clean nulls", "Plot charts"], "B"),
                ("Which of these is a classification algorithm?",
                 ["Linear Regression", "K-Means", "Logistic Regression", "PCA"], "C"),
            ]),
        ],
    },
    {
        "title": "AI & Generative AI", "slug": "ai-generative-ai", "fee": 70000,
        "banner": "ai-generative.png",
        "short": "LLMs, prompt engineering, RAG and building real GenAI apps.",
        "desc": "<p>Go from curious to builder: how LLMs work, prompt engineering, embeddings, <b>RAG pipelines</b>, and shipping production GenAI apps with APIs.</p>",
        "modules": [
            ("LLM Fundamentals & Prompting", [
                ("How Large Language Models Work", "text",
                 "<p>Tokens, transformers and training — the mental model every AI engineer needs.</p>"),
                ("Prompt Engineering Masterclass (Live Demo)", "video", ""),
                ("Prompt Patterns Library", "text",
                 "<p>Copy-paste prompt templates for coding, writing, analysis and automation.</p>"),
            ]),
            ("Building GenAI Apps", [
                ("RAG: Chat With Your Documents", "text",
                 "<p>Embeddings, vector databases and retrieval pipelines explained simply.</p>"),
                ("Build a Chatbot With APIs (Live Demo)", "video", ""),
                ("Deploying & Evaluating AI Apps", "text",
                 "<p>Cost control, evals, guardrails and taking your app to production.</p>"),
            ]),
        ],
        "quiz": [
            ("Module 1 Quiz", [
                ("A 'token' in an LLM is best described as…",
                 ["A coin used for payment", "A chunk of text the model processes",
                  "A password", "A type of neural layer"], "B"),
                ("Which technique gives an LLM access to your private documents?",
                 ["Fine-tuning only", "RAG", "More GPUs", "Longer prompts"], "B"),
            ]),
            ("Module 2 Quiz", [
                ("Embeddings are…",
                 ["Vector representations of text", "Image filters",
                  "API keys", "Prompt templates"], "A"),
                ("A guardrail in a GenAI app is used to…",
                 ["Speed up inference", "Keep outputs safe and on-topic",
                  "Reduce API cost to zero", "Train the model"], "B"),
            ]),
        ],
    },
    {
        "title": "Python Programming", "slug": "python-programming", "fee": 35000,
        "banner": "python.png",
        "short": "From zero to job-ready Python developer with projects.",
        "desc": "<p>The perfect first programming course: <b>Python from scratch</b> — syntax, OOP, files, APIs — plus 5 portfolio projects and interview prep.</p>",
        "modules": [
            ("Python Basics", [
                ("Your First Python Program", "text",
                 "<p>Install Python, write your first script, and understand variables and data types.</p>"),
                ("Live Coding: Loops & Functions (Live Demo)", "video", ""),
                ("Practice Workbook 1", "text",
                 "<p>20 exercises on strings, lists, dicts and control flow with solutions.</p>"),
            ]),
            ("OOP & Real Projects", [
                ("Object-Oriented Python", "text",
                 "<p>Classes, objects, inheritance — explained with real-world analogies.</p>"),
                ("Build a Web Scraper (Live Demo)", "video", ""),
                ("Final Project Brief", "text",
                 "<p>Build and document one portfolio-ready project with a guided checklist.</p>"),
            ]),
        ],
        "quiz": [
            ("Module 1 Quiz", [
                ("Which of these is a valid Python variable name?",
                 ["2cool", "_cool2", "cool-2", "class"], "B"),
                ("What does len([1, 2, 3]) return?", ["2", "3", "6", "Error"], "B"),
            ]),
            ("Module 2 Quiz", [
                ("In OOP, a 'class' is…",
                 ["A function", "A blueprint for objects", "A file", "A loop"], "B"),
                ("Which keyword creates a function in Python?",
                 ["func", "def", "function", "lambda only"], "B"),
            ]),
        ],
    },
    {
        "title": "Data Analytics", "slug": "data-analytics", "fee": 40000,
        "banner": "data-analytics.png",
        "short": "Excel, SQL, Power BI and storytelling with data.",
        "desc": "<p>Become a <b>Data Analyst</b>: Excel mastery, SQL from zero, Power BI dashboards, and presenting insights that drive business decisions.</p>",
        "modules": [
            ("Excel & SQL", [
                ("Excel Like an Analyst", "text",
                 "<p>PivotTables, VLOOKUP/XLOOKUP, and formulas analysts use every day.</p>"),
                ("SQL From Zero (Live Demo)", "video", ""),
                ("SQL Practice Dataset Guide", "text",
                 "<p>Joins, GROUP BY and subqueries with a real e-commerce dataset.</p>"),
            ]),
            ("Power BI & Storytelling", [
                ("Build Your First Dashboard", "text",
                 "<p>Connect data, model it, and design dashboards people actually read.</p>"),
                ("Dashboard Design Review (Live Demo)", "video", ""),
                ("Presenting Insights", "text",
                 "<p>How to turn charts into a story that gets you hired.</p>"),
            ]),
        ],
        "quiz": [
            ("Module 1 Quiz", [
                ("Which SQL clause filters grouped rows?",
                 ["WHERE", "HAVING", "ORDER BY", "LIMIT"], "B"),
                ("A PivotTable is mainly used to…",
                 ["Write code", "Summarize large data fast", "Send emails", "Design logos"], "B"),
            ]),
            ("Module 2 Quiz", [
                ("The best chart for showing trends over time is…",
                 ["Pie chart", "Line chart", "Donut chart", "Word cloud"], "B"),
                ("In Power BI, DAX is used for…",
                 ["Data cleaning only", "Custom calculations and measures",
                  "User logins", "Exporting PDFs"], "B"),
            ]),
        ],
    },
    {
        "title": "Linux Administration", "slug": "linux-administration", "fee": 25000,
        "banner": "linux.png",
        "short": "Command line, servers, shell scripting and system admin skills.",
        "desc": "<p>Own the terminal: <b>Linux from zero to sysadmin</b> — command line, users, permissions, services, and bash scripting for real servers.</p>",
        "modules": [
            ("Command Line Mastery", [
                ("Navigating the Filesystem", "text",
                 "<p>ls, cd, paths, and thinking in the terminal.</p>"),
                ("Live Terminal Session (Live Demo)", "video", ""),
                ("Essential Commands Reference", "text",
                 "<p>50 commands every admin types without thinking.</p>"),
            ]),
            ("System Administration", [
                ("Users, Permissions & Services", "text",
                 "<p>chmod, systemd, and keeping a server healthy.</p>"),
                ("Server Setup Walkthrough (Live Demo)", "video", ""),
                ("Bash Scripting Basics", "text",
                 "<p>Automate boring tasks with your first scripts.</p>"),
            ]),
        ],
        "quiz": [
            ("Module 1 Quiz", [
                ("Which command lists files in Linux?", ["dir", "ls", "list", "show"], "B"),
                ("The root user's home directory is…",
                 ["/home", "/root", "/admin", "/usr"], "B"),
            ]),
            ("Module 2 Quiz", [
                ("chmod 755 on a file gives…",
                 ["Full access to everyone", "rwx for owner, rx for others",
                  "No access", "Read-only for all"], "B"),
                ("Which tool manages services on modern Linux?",
                 ["init.d", "systemd", "cron", "apt"], "B"),
            ]),
        ],
    },
    {
        "title": "DevOps", "slug": "devops", "fee": 45000,
        "banner": "devops.png",
        "short": "CI/CD, Docker, Kubernetes and cloud deployment pipelines.",
        "desc": "<p>Ship software like a pro: <b>Git, CI/CD, Docker, Kubernetes</b> and cloud deployments — with a complete pipeline project.</p>",
        "modules": [
            ("CI/CD & Docker", [
                ("How DevOps Teams Ship Code", "text",
                 "<p>Pipelines, environments, and the DevOps mindset.</p>"),
                ("Docker Hands-On (Live Demo)", "video", ""),
                ("Dockerfile Patterns Guide", "text",
                 "<p>Multi-stage builds and image best practices.</p>"),
            ]),
            ("Kubernetes & Cloud", [
                ("Kubernetes Concepts", "text",
                 "<p>Pods, deployments and services — finally explained clearly.</p>"),
                ("Deploy to the Cloud (Live Demo)", "video", ""),
                ("Capstone: Full Pipeline", "text",
                 "<p>Build a CI/CD pipeline that deploys a real app.</p>"),
            ]),
        ],
        "quiz": [
            ("Module 1 Quiz", [
                ("A Docker image is…",
                 ["A running process", "A read-only template for containers",
                  "A virtual machine", "A code editor"], "B"),
                ("CI in CI/CD stands for…",
                 ["Central Internet", "Continuous Integration",
                  "Cloud Infrastructure", "Code Inspection"], "B"),
            ]),
            ("Module 2 Quiz", [
                ("In Kubernetes, a Pod is…",
                 ["A storage bucket", "The smallest deployable unit",
                  "A load balancer", "A DNS record"], "B"),
                ("kubectl is used to…",
                 ["Write Dockerfiles", "Interact with a Kubernetes cluster",
                  "Install Linux", "Monitor GPUs"], "B"),
            ]),
        ],
    },
    {
        "title": "Cyber Security & Ethical Hacking", "slug": "cyber-security-ethical-hacking",
        "fee": 60000, "banner": "ethical-hacking.png",
        "short": "Ethical hacking, penetration testing and security careers.",
        "desc": "<p>Think like an attacker, defend like a pro: <b>ethical hacking</b> labs, penetration testing methodology, and a career roadmap into cybersecurity.</p>",
        "modules": [
            ("Hacking Fundamentals (Ethical)", [
                ("The Ethical Hacker's Mindset", "text",
                 "<p>Scope, permission and the law — hacking done right.</p>"),
                ("Lab Setup & Recon (Live Demo)", "video", ""),
                ("Networking for Hackers", "text",
                 "<p>TCP/IP, ports and protocols from an attacker's view.</p>"),
            ]),
            ("Penetration Testing", [
                ("Vulnerability Scanning", "text",
                 "<p>Finding weaknesses methodically with professional tools.</p>"),
                ("Exploitation Lab (Live Demo)", "video", ""),
                ("Writing a Pentest Report", "text",
                 "<p>Turn findings into a report clients pay for.</p>"),
            ]),
        ],
        "quiz": [
            ("Module 1 Quiz", [
                ("Ethical hacking always requires…",
                 ["Speed", "Written permission / scope", "Expensive tools", "A hoodie"], "B"),
                ("Which tool is used for network scanning?",
                 ["Photoshop", "Nmap", "Excel", "Slack"], "B"),
            ]),
            ("Module 2 Quiz", [
                ("A vulnerability scan…",
                 ["Deletes data", "Identifies known weaknesses",
                  "Installs malware", "Cracks passwords"], "B"),
                ("The final deliverable of a pentest is…",
                 ["A trophy", "A professional report", "A virus", "Nothing"], "B"),
            ]),
        ],
    },
]

BONUS_COURSES = [
    {
        "title": "Git & GitHub Essentials", "slug": "git-github-essentials", "fee": 0,
        "banner": "", "short": "FREE bonus: version control every developer must know.",
        "desc": "<p><b>Free value-added course:</b> Git basics, branching, and collaborating on GitHub.</p>",
        "modules": [("Git Basics", [
            ("Install & First Commit", "text", "<p>Your first repository in 10 minutes.</p>"),
            ("Branching (Live Demo)", "video", ""),
        ])],
        "quiz": [("Git Quiz", [
            ("Which command creates a new Git repository?",
             ["git start", "git init", "git new", "git create"], "B")])],
    },
    {
        "title": "Prompt Engineering Basics", "slug": "prompt-engineering-basics", "fee": 0,
        "banner": "", "short": "FREE bonus: get 10x more from AI tools.",
        "desc": "<p><b>Free value-added course:</b> practical prompting for ChatGPT, Gemini and Claude.</p>",
        "modules": [("Prompting Foundations", [
            ("Anatomy of a Great Prompt", "text", "<p>Role, context, task, format.</p>"),
            ("Live Prompting Session (Live Demo)", "video", ""),
        ])],
        "quiz": [("Prompting Quiz", [
            ("Giving the AI a role (e.g. 'act as a tutor') helps because…",
             ["It looks cool", "It steers tone and expertise",
              "It is required", "It saves tokens only"], "B")])],
    },
]

ASSIGNMENTS = {
    "data-science": [("Exploratory Data Analysis Project",
                      "Analyze the provided sales dataset: clean it, visualize 5 insights, and submit a PDF report.", 100)],
    "ai-generative-ai": [("Build a RAG Chatbot",
                           "Build a chatbot that answers questions from a PDF using any LLM API. Submit code + demo video link.", 100)],
    "python-programming": [("Portfolio Project",
                             "Build one complete Python project (scraper, automation or game) with a README. Submit a zip.", 100)],
    "data-analytics": [("Sales Dashboard",
                        "Build a Power BI dashboard from the sales dataset and submit the .pbix + 1-page insight summary.", 100)],
    "linux-administration": [("Server Hardening Checklist",
                               "Harden a Linux VM: users, SSH, firewall. Submit your checklist + screenshots PDF.", 100)],
    "devops": [("CI/CD Pipeline",
                 "Create a CI/CD pipeline for a sample app using GitHub Actions + Docker. Submit repo link.", 100)],
    "cyber-security-ethical-hacking": [("Vulnerability Assessment Report",
                                         "Scan the practice lab VM and write a professional pentest-style report (PDF).", 100)],
}


def get_or_create(model, defaults=None, **kw):
    obj = model.query.filter_by(**kw).first()
    if obj:
        return obj, False
    obj = model(**kw, **(defaults or {}))
    db.session.add(obj)
    db.session.flush()
    return obj, True


with app.app_context():
    # ---- demo users ----
    users = [
        ("Admin User", "admin@sayyed.in", "admin123", "admin"),
        ("Manager User", "manager@sayyed.in", "manager123", "manager"),
        ("Faculty User", "faculty@sayyed.in", "faculty123", "faculty"),
        ("Counsellor User", "counsellor@sayyed.in", "counsellor123", "counsellor"),
        ("Student User", "student@sayyed.in", "student123", "student"),
    ]
    user_map = {}
    for name, email, pw, role in users:
        u = User.query.filter_by(email=email).first()
        if not u:
            u = User(name=name, email=email, role=role)
            u.set_password(pw)
            db.session.add(u)
        user_map[role] = u
    db.session.commit()

    faculty = user_map["faculty"]

    # ---- courses ----
    def seed_course(data, is_bonus=False, instructor=None):
        course, _ = get_or_create(
            Course,
            {"title": data["title"], "short_desc": data["short"],
             "description": data["desc"], "fee": data["fee"],
             "is_bonus": is_bonus, "banner": data.get("banner", "")},
            slug=data["slug"])
        if instructor and not course.instructor_id:
            course.instructor_id = instructor.id
        for mi, (mtitle, lessons) in enumerate(data["modules"]):
            module, _ = get_or_create(
                Module, {"position": mi},
                course_id=course.id, title=mtitle)
            for li, (ltitle, kind, body) in enumerate(lessons):
                lesson, _ = get_or_create(
                    Lesson,
                    {"position": li, "kind": kind, "body": body},
                    module_id=module.id, title=ltitle)
                # drip schedule: lesson 2 unlocks after 7 days, lesson 3 after 14
                want_drip = 7 if li == 1 else (14 if li == 2 else 0)
                if lesson.available_after_days != want_drip:
                    lesson.available_after_days = want_drip
            for qi, (qtitle, questions) in enumerate(data["quiz"]):
                if qi != mi:
                    continue
                quiz, _ = get_or_create(
                    Quiz, {"pass_percent": 60}, module_id=module.id, title=qtitle)
                for qpos, (qtext, opts, correct) in enumerate(questions):
                    get_or_create(
                        Question,
                        {"option_a": opts[0], "option_b": opts[1],
                         "option_c": opts[2], "option_d": opts[3],
                         "correct": correct, "position": qpos},
                        quiz_id=quiz.id, text=qtext)
        # recordings
        for ri in range(1, 3):
            get_or_create(
                Recording,
                {"video_url": "", "duration_min": 60,
                 "recorded_on": date.today() - timedelta(days=7 * ri)},
                course_id=course.id, title=f"Live Class {ri}: {data['title']} — Session {ri}")
        db.session.commit()
        return course

    for c in COURSES:
        instr = faculty if c["slug"] in ("python-programming", "data-science") else None
        seed_course(c, instructor=instr)

    for c in BONUS_COURSES:
        seed_course(c, is_bonus=True)

    # ---- assignments ----
    for slug, assigns in ASSIGNMENTS.items():
        course = Course.query.filter_by(slug=slug).first()
        for title, desc, marks in assigns:
            get_or_create(
                Assignment,
                {"description": desc, "max_marks": marks,
                 "due_date": date.today() + timedelta(days=14),
                 "created_by": user_map["admin"].id},
                course_id=course.id, title=title)
    db.session.commit()

    # ---- coupons ----
    for code, pct in (("WELCOME10", 10), ("FLAT20", 20)):
        get_or_create(Coupon, {"percent_off": pct, "active": True}, code=code)
    db.session.commit()

    # ---- live sessions (always upcoming; refreshed on re-run) ----
    admin = user_map["admin"]
    now = datetime.utcnow()
    live_plan = [
        ("data-science",
         "Data Science — Week 3 Doubt-Clearing Live Class",
         now + timedelta(days=1, hours=2), 60),
        ("ai-generative-ai",
         "AI & Generative AI — Prompt Engineering Workshop (Live)",
         now + timedelta(days=2, hours=4), 90),
    ]
    for slug, title, starts_at, duration in live_plan:
        course = Course.query.filter_by(slug=slug).first()
        sess = LiveSession.query.filter_by(title=title).first()
        if sess:
            sess.starts_at = starts_at
            sess.duration_min = duration
            sess.sent_reminder = False
        else:
            import secrets
            sess = LiveSession(
                course_id=course.id, title=title, starts_at=starts_at,
                duration_min=duration, created_by=admin.id,
                room_name=f"se-{slug}-{secrets.token_hex(3)}")
            db.session.add(sess)
    db.session.commit()

    # ---- announcement ----
    ann = Announcement.query.filter_by(title="Admissions open — October batch").first()
    if not ann:
        db.session.add(Announcement(
            title="Admissions open — October batch",
            body="New batches for all 7 courses start soon. Enroll now and use code WELCOME10 for 10% off!",
            active=True))
    db.session.commit()

    print("Seed complete:")
    print(f"  users: {User.query.count()}, courses: {Course.query.count()}, "
          f"modules: {Module.query.count()}, lessons: {Lesson.query.count()}, "
          f"quizzes: {Quiz.query.count()}, questions: {Question.query.count()}, "
          f"assignments: {Assignment.query.count()}, recordings: {Recording.query.count()}, "
          f"coupons: {Coupon.query.count()}, live_sessions: {LiveSession.query.count()}, "
          f"announcements: {Announcement.query.count()}")
