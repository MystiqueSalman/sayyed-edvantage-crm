# Stream 2 (Learning extras) — 84/84 green
Files: app/models13_learning.py, app/learn13.py (learn13_bp), app/video13.py, 9 templates (p13_notes_list, p13_note_form, p13_sql_list, p13_sql_detail, p13_ds_list, p13_ds_detail, p13_versions, p13_video_policy, p13_video_watch), datasets in app/static/datasets/, test_phase13_learning.py
Modified (allowed): lesson.html (signed video URL), manage_course.html (versions panel), manage_lesson_form.html (video policy editor), developers.html (video security docs)
Tables (8):
- lesson_notes13: id PK, user_id INT FK users.id NOT NULL idx, lesson_id INT FK lessons.id NOT NULL idx, title VARCHAR(160) default '', body TEXT default '', created_at DateTime, updated_at DateTime, UQ(user_id, lesson_id)
- sql_exercises13: id PK, title VARCHAR(160) NOT NULL, description TEXT default '', setup_sql TEXT default '', expected_sql TEXT default '', hint VARCHAR(300) default '', active BOOL default True, created_at DateTime
- sql_attempts13: id PK, user_id INT FK users.id NOT NULL idx, exercise_id INT FK sql_exercises13.id NOT NULL idx, query TEXT (attr sql_query) default '', passed BOOL default False, created_at DateTime
- ds_exercises13: id PK, title VARCHAR(160) NOT NULL, description TEXT default '', steps JSON default [], active BOOL default True, sort_order INT default 0, created_at DateTime
- ds_progress13: id PK, user_id INT FK users.id NOT NULL idx, exercise_id INT FK ds_exercises13.id NOT NULL idx, step_idx INT default 0, passed BOOL default False, output TEXT default '', created_at/updated_at DateTime, UQ(user_id, exercise_id, step_idx)
- course_versions13: id PK, course_id INT FK courses.id NOT NULL idx, version_no INT NOT NULL, snapshot JSON default {}, note VARCHAR(300) default '', created_by INT FK users.id NULL, created_at DateTime, UQ(course_id, version_no)
- enrollment_versions13: id PK, enrollment_id INT FK enrollments.id NOT NULL UNIQUE idx, version_id INT FK course_versions13.id NULL, linked_at DateTime
- video_policies13: id PK, lesson_id INT FK lessons.id NOT NULL UNIQUE idx, allow_download BOOL default False, token_expiry_hours INT default 2, updated_at DateTime
Note: after_insert listener on Enrollment links new enrollments to latest version (in models13_learning.py; active once module imported).
Blueprint: from .learn13 import learn13_bp; app.register_blueprint(learn13_bp)
Seed: ensure_learning13_defaults() in app/learn13.py (SQL + DS exercises) — wire into create_app like other ensure_* hooks.
Nav snippets: student: /notes, /labs/sql, /labs/datascience; faculty: versions panel on manage course page.
