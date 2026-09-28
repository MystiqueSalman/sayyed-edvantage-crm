"""Phase 12 §21.4 — coding labs: safe in-browser Python execution.

Sandbox layers (defense in depth, stdlib only):
  1. AST scan — rejects dangerous imports (os, sys, subprocess, socket,
     shutil, pathlib, importlib, ctypes, threading, multiprocessing,
     urllib, http, requests, ...) and dangerous names (__import__, eval,
     exec, compile, open, globals, locals, vars, dir, help).
  2. Subprocess with a hard timeout (5s) in an empty temp working dir.
  3. preexec_fn resource limits: 256MB address space, 10s CPU, 1MB files.
  4. Minimal environment (no secrets inherited).
  5. Output truncated to 20KB.

This is a teaching sandbox, not a bulletproof jail — it is safe for
trusted students running lesson exercises, which is the documented scope.
"""
import ast
import os
import resource
import subprocess
import sys
import tempfile

BLOCKED_IMPORTS = {
    "os", "sys", "subprocess", "socket", "shutil", "pathlib", "importlib",
    "ctypes", "threading", "multiprocessing", "signal", "urllib", "http",
    "requests", "ftplib", "smtplib", "telnetlib", "webbrowser", "pty",
    "pwd", "grp", "resource", "gc", "inspect", "ast", "io", "codecs",
    "pickle", "marshal", "shelve", "dbm", "sqlite3", "builtins",
}

BLOCKED_NAMES = {
    "__import__", "eval", "exec", "compile", "open", "globals", "locals",
    "vars", "dir", "help", "input", "breakpoint", "exit", "quit",
    "memoryview",
}

RUN_TIMEOUT = 5
MAX_OUTPUT = 20_000


class UnsafeCode(Exception):
    pass


def _scan(code):
    """Raise UnsafeCode if the AST uses blocked imports/names."""
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise UnsafeCode(f"Syntax error: {exc}")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in BLOCKED_IMPORTS:
                    raise UnsafeCode(f"Import of '{alias.name}' is not allowed")
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root in BLOCKED_IMPORTS:
                raise UnsafeCode(f"Import from '{node.module}' is not allowed")
        elif isinstance(node, ast.Name) and node.id in BLOCKED_NAMES:
            raise UnsafeCode(f"Use of '{node.id}' is not allowed")
        elif isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise UnsafeCode("Dunder attribute access is not allowed")


def _limit_resources():
    try:
        resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024,) * 2)
        resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
        resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024,) * 2)
        resource.setrlimit(resource.RLIMIT_NPROC, (16, 16))
    except Exception:
        pass


def run_python_code(code):
    """Execute student code safely. Returns (ok, output, error)."""
    code = (code or "")[:50_000]
    try:
        _scan(code)
    except UnsafeCode as exc:
        return False, "", str(exc)
    with tempfile.TemporaryDirectory(prefix="se_lab_") as tmp:
        src = os.path.join(tmp, "main.py")
        with open(src, "w", encoding="utf-8") as fh:
            fh.write(code)
        env = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8",
               "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8"}
        try:
            proc = subprocess.run(
                [sys.executable, "-I", "-c",
                 "import runpy,sys; sys.argv=['main.py']; "
                 "runpy.run_path('main.py', run_name='__main__')"],
                cwd=tmp, env=env, capture_output=True, text=True,
                timeout=RUN_TIMEOUT, preexec_fn=_limit_resources)
        except subprocess.TimeoutExpired:
            return False, "", f"Time limit exceeded ({RUN_TIMEOUT}s)"
        except Exception as exc:
            return False, "", f"Runner error: {exc}"
    out = (proc.stdout or "")[:MAX_OUTPUT]
    err = (proc.stderr or "")[:MAX_OUTPUT]
    if proc.returncode != 0:
        # surface the last line of the traceback as the error
        last = [ln for ln in err.strip().splitlines() if ln.strip()]
        return False, out, last[-1] if last else f"Exit code {proc.returncode}"
    return True, out, ""


def normalize_output(text):
    """Normalize for auto-check: strip trailing space per line + edges."""
    lines = (text or "").replace("\r\n", "\n").split("\n")
    lines = [ln.rstrip() for ln in lines]
    return "\n".join(lines).strip("\n")


def check_output(actual, expected):
    """True when the student's output matches the expected output."""
    if not (expected or "").strip():
        return True  # no expected output => any successful run passes
    return normalize_output(actual) == normalize_output(expected)
