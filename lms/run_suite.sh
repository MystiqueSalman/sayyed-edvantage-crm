#!/bin/bash
# Run one test suite against a fresh isolated SQLite DB.
# Usage: ./run_suite.sh <test_file_without_.py> [port]
set -u
SUITE="${1:?usage: run_suite.sh <suite> [port]}"
PORT="${2:-5000}"
LMS=~/workspace/lms
DB="/tmp/lms_${SUITE}.db"
rm -f "$DB"
export SQLITE_PATH="$DB" LMS_SCHEDULER=off
cd "$LMS" || exit 1
echo "== migrate $DB"
LMS_SKIP_CREATE_ALL=1 ./venv/bin/flask db upgrade > /tmp/mig_${SUITE}.log 2>&1 || { tail -20 /tmp/mig_${SUITE}.log; exit 1; }
echo "== seed"
./venv/bin/python seed.py > /tmp/seed_${SUITE}.log 2>&1 || { tail -20 /tmp/seed_${SUITE}.log; exit 1; }
echo "== start server :$PORT"
PORT="$PORT" ./venv/bin/python -c "
import os
from app import create_app
app = create_app()
app.run(host='127.0.0.1', port=int(os.environ['PORT']), debug=False, use_reloader=False)
" > /tmp/srv_${SUITE}.log 2>&1 &
SRVPID=$!
for i in $(seq 1 30); do
  curl -s -o /dev/null --max-time 2 "http://127.0.0.1:$PORT/" && break
  sleep 1
done
echo "== run $SUITE"
./venv/bin/python "${SUITE}.py"
RC=$?
echo "== kill server $SRVPID"
kill "$SRVPID" 2>/dev/null
wait "$SRVPID" 2>/dev/null
exit $RC
