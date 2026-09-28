# Stream 3 (AI extras) — 74/74 green
Files: app/models13_ai.py, app/memory13.py, app/atrisk13.py, app/ai13.py (ai13_bp), 9 templates (p13_ai_assistant, p13_draft_detail, p13_draft_edit, p13_rubrics, p13_evaluate, p13_evaluations, p13_student_evaluations, p13_atrisk, p13_memory), test_phase13_ai.py
Tables:
- ai_drafts13: id PK, faculty_id FK users.id NULL, course_id FK courses.id NULL, kind varchar(20), topic varchar(200), content text, status varchar(20) DEFAULT 'draft', created_at datetime
- rubrics13: id PK, name varchar(160), course_id FK courses.id NULL, project_id FK projects.id NULL, criteria JSON DEFAULT [], created_by FK users.id NULL, created_at datetime
- project_evaluations13: id PK, project_submission_id FK project_submissions.id, rubric_id FK rubrics13.id, scores JSON DEFAULT {}, feedback_text text, status varchar(20) DEFAULT 'pending_review', evaluated_at datetime, reviewed_by FK users.id NULL, reviewed_at datetime NULL
- atrisk_flags13: id PK, user_id FK users.id, reasons JSON DEFAULT [], created_at datetime, resolved boolean DEFAULT false, resolved_at datetime NULL
- student_memory13: id PK, user_id FK users.id UNIQUE, completed_topics JSON, weak_topics JSON, strengths JSON, preferences JSON, updated_at datetime
Blueprint: from .ai13 import ai13_bp; app.register_blueprint(ai13_bp)
Tutor injection snippet: from app.ai13 import memory_context_text; prompt += "\n\n" + memory_context_text(user.id)
Nav snippets: faculty: ai13.ai_assistant (AI Assistant), ai13.evaluations (AI Evaluations); counsellor: ai13.at_risk (At-Risk); student: ai13.student_evaluations, ai13.student_memory (My Memory)
Settings: none new (uses OPENAI_API_KEY + ai_settings). Requirements: none.
Regressions: test_phase6 50/50, test_phase9 68/68, test_phase12 88/88 green.
Caveats: quiz-draft auto-import intentionally disabled (no draft flag on Quiz); no "AI evaluate" button on existing submissions template (add link optionally).
