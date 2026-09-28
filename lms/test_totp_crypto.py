"""TOTP secrets encrypted at rest — security hardening follow-up.

Runs in-process against the FRESH DB prepared by run_suite.sh (migrations
via `flask db upgrade`; SECRET_KEY is exported by run_suite.sh).

Coverage:
  - round-trip encrypt/decrypt; ciphertext shape; never plaintext
  - is_encrypted() detection (ciphertext vs legacy plaintext)
  - legacy plaintext passes through decrypt (graceful rollout reads)
  - corrupt ciphertext fails closed (RuntimeError, no garbage)
  - wrong SECRET_KEY cannot decrypt (fail closed)
  - backfill encrypts legacy plaintext in place; idempotent; skips encrypted
  - end-to-end: stored secret verifies a live pyotp code after decrypt
  - fail-closed: create_app() refuses to boot without SECRET_KEY
    (in-process + real subprocess), clear error message naming SECRET_KEY
  - `flask backfill-totp-secrets` CLI command is registered
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import create_app, db  # noqa: E402
from app.models import User  # noqa: E402
from app.models13_auth import UserSecurity13  # noqa: E402
from app import totp_crypto as TC  # noqa: E402

LMS_DIR = os.path.dirname(os.path.abspath(__file__))

app = create_app()
with app.app_context():
    db.create_all()  # ensure p13 tables exist on the harness DB
passed, failed, notes = 0, 0, []


def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  PASS {name}")
    else:
        failed += 1
        notes.append(name)
        print(f"  FAIL {name} {detail}")


def ctx():
    return app.app_context()


# --- 1. round-trip -----------------------------------------------------------
import pyotp  # noqa: E402

plain = pyotp.random_base32()
token = TC.encrypt_totp_secret(plain)
check("round-trip decrypt returns original", TC.decrypt_totp_secret(token) == plain)
check("ciphertext is not plaintext", token != plain)
check("ciphertext looks like a Fernet token", token.startswith("gAAAAA"), token[:12])
check("is_encrypted(ciphertext) is True", TC.is_encrypted(token) is True)
check("is_encrypted(plaintext) is False", TC.is_encrypted(plain) is False)
check("legacy plaintext passes through decrypt (graceful read)",
      TC.decrypt_totp_secret(plain) == plain)

# --- 2. corrupt / wrong-key fail closed --------------------------------------
try:
    TC.decrypt_totp_secret("gAAAAA-this-is-not-valid-ciphertext")
    check("corrupt ciphertext raises", False)
except RuntimeError as e:
    check("corrupt ciphertext raises RuntimeError", True)
    check("corrupt error gives no secret material", "gAAAAA" not in str(e))
except Exception as e:  # noqa: BLE001
    check("corrupt ciphertext raises RuntimeError", False, type(e).__name__)

old_key = os.environ.get("SECRET_KEY")
os.environ["SECRET_KEY"] = "a-completely-different-test-key-12345"
try:
    check("wrong key: is_encrypted is False", TC.is_encrypted(token) is False)
    try:
        TC.decrypt_totp_secret(token)
        check("wrong key: decrypt raises", False)
    except RuntimeError:
        check("wrong key: decrypt raises RuntimeError", True)
    # encrypt under the new key round-trips under the new key
    t2 = TC.encrypt_totp_secret(plain)
    check("new key round-trip works", TC.decrypt_totp_secret(t2) == plain)
    check("different keys give different ciphertext", t2 != token)
finally:
    if old_key is None:
        os.environ.pop("SECRET_KEY", None)
    else:
        os.environ["SECRET_KEY"] = old_key

try:
    TC.encrypt_totp_secret("")
    check("empty secret rejected", False)
except ValueError:
    check("empty secret rejected", True)

# --- 3. backfill -------------------------------------------------------------
def make_user(email):
    with ctx():
        u = User(name="TOTP Crypto", email=email, role="student")
        u.set_password("secret123")
        db.session.add(u)
        db.session.commit()
        return u.id

uid = make_user("totpcrypto@x.com")
legacy = pyotp.random_base32()
with ctx():
    # Simulate a pre-hardening row: plaintext written directly, bypassing encrypt.
    row = UserSecurity13(user_id=uid, totp_secret=legacy, mfa_enabled=True)
    db.session.add(row)
    db.session.commit()

with ctx():
    n = TC.backfill_totp_secrets()
check("backfill encrypts 1 legacy row", n == 1, f"got {n}")
with ctx():
    row = UserSecurity13.query.filter_by(user_id=uid).first()
    stored = row.totp_secret
check("backfilled value is no longer plaintext", stored != legacy)
check("backfilled value is encrypted", TC.is_encrypted(stored) is True)
check("backfilled value decrypts to original", TC.decrypt_totp_secret(stored) == legacy)
check("backfilled row still verifies live codes",
      pyotp.TOTP(TC.decrypt_totp_secret(stored)).verify(pyotp.TOTP(legacy).now(),
                                                        valid_window=1))
with ctx():
    before = UserSecurity13.query.filter_by(user_id=uid).first().totp_secret
    n2 = TC.backfill_totp_secrets()
    after = UserSecurity13.query.filter_by(user_id=uid).first().totp_secret
check("backfill idempotent (0 on second run)", n2 == 0, f"got {n2}")
check("backfill does not double-encrypt", before == after)

# --- 4. end-to-end: encrypt-on-write path stores ciphertext ------------------
uid2 = make_user("totpcrypto2@x.com")
secret2 = pyotp.random_base32()
with ctx():
    db.session.add(UserSecurity13(user_id=uid2,
                                  totp_secret=TC.encrypt_totp_secret(secret2),
                                  mfa_enabled=True))
    db.session.commit()
with ctx():
    s = UserSecurity13.query.filter_by(user_id=uid2).first().totp_secret
check("write path stores ciphertext, not plaintext", s != secret2 and s.startswith("gAAAAA"))
check("read path decrypts for verification",
      pyotp.TOTP(TC.decrypt_totp_secret(s)).verify(pyotp.TOTP(secret2).now(),
                                                   valid_window=1))

# --- 5. fail-closed without SECRET_KEY ---------------------------------------
saved = os.environ.pop("SECRET_KEY", None)
try:
    try:
        TC.require_totp_encryption()
        check("require_totp_encryption raises without SECRET_KEY", False)
    except TC.MissingTotpKeyError as e:
        check("require_totp_encryption raises MissingTotpKeyError", True)
        check("error message names SECRET_KEY", "SECRET_KEY" in str(e), str(e)[:60])
    try:
        TC.encrypt_totp_secret(pyotp.random_base32())
        check("encrypt raises without SECRET_KEY (no silent plaintext)", False)
    except TC.MissingTotpKeyError:
        check("encrypt raises without SECRET_KEY (no silent plaintext)", True)
finally:
    if saved is not None:
        os.environ["SECRET_KEY"] = saved

# Real subprocess: env genuinely lacks SECRET_KEY -> create_app must not boot.
env = {k: v for k, v in os.environ.items() if k != "SECRET_KEY"}
proc = subprocess.run(
    [sys.executable, "-c", "from app import create_app; create_app()"],
    cwd=LMS_DIR, env=env, capture_output=True, text=True, timeout=120)
check("create_app refuses to boot without SECRET_KEY", proc.returncode != 0,
      f"exit={proc.returncode}")
check("startup error names SECRET_KEY",
      "SECRET_KEY" in (proc.stderr or ""), (proc.stderr or "")[-200:])

# --- 6. CLI command registered ------------------------------------------------
check("flask backfill-totp-secrets command registered",
      "backfill-totp-secrets" in app.cli.commands)

print(f"\n{passed} passed, {failed} failed")
if notes:
    print("FAILED:", notes)
sys.exit(1 if failed else 0)
