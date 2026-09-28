# Stream 4 (Messaging + Leaderboard) — 57/57 green
Files: app/models13_social.py, app/social13.py (social13_bp), templates p13_inbox.html, p13_new.html, p13_thread.html, p13_leaderboard.html, test_phase13_social.py
Tables:
- dm_conversations: id PK, student_id FK users.id NOT NULL INDEX, faculty_id FK users.id NOT NULL INDEX, subject VARCHAR(160) NOT NULL DEFAULT '', created_at DATETIME NOT NULL, archived BOOLEAN NOT NULL DEFAULT FALSE, last_message_at DATETIME NULL
- dm_messages: id PK, conversation_id FK dm_conversations.id NOT NULL INDEX, sender_id FK users.id NOT NULL, body TEXT NOT NULL, created_at DATETIME NOT NULL, read_at DATETIME NULL
- leaderboard_privacy: id PK, user_id FK users.id UNIQUE NOT NULL INDEX, leaderboard_opt_out BOOLEAN NOT NULL DEFAULT FALSE, updated_at DATETIME NULL
Blueprint: from .social13 import social13_bp; app.register_blueprint(social13_bp)
Nav snippets: <a href="{{ url_for('social13.inbox') }}">💬 Messages{% if dm_unread %}... (inject dm_unread via unread_dm_count in _inject_globals); public <a href="{{ url_for('social13.leaderboard') }}">🏆 Leaderboard</a>
Profile opt-out: no profile.html exists — toggle available at POST /leaderboard/privacy meanwhile.
Settings keys: none. Requirements: none.
Caveats: needs tables in combined migration; test isolation quirk resolved.
