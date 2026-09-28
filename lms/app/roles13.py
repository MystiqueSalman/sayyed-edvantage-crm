"""Phase 13 — extended role constants (Stream 1: auth).

The base ROLES tuple lives in app/models.py and must stay untouched;
these new roles extend it. The Phase 9 permission matrix in
app/operations.py gives each role its defaults.
"""
ROLE_PARENT = "parent"
ROLE_PLACEMENT_OFFICER = "placement_officer"
ROLE_FINANCE_OFFICER = "finance_officer"
ROLE_CONTENT_MANAGER = "content_manager"
ROLE_SUPER_ADMIN = "super_admin"

EXTENDED_ROLES = (
    ROLE_PARENT,
    ROLE_PLACEMENT_OFFICER,
    ROLE_FINANCE_OFFICER,
    ROLE_CONTENT_MANAGER,
    ROLE_SUPER_ADMIN,
)
