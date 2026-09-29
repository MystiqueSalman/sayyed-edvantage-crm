#!/bin/bash
# Run every LMS suite sequentially on fresh isolated DBs (port 5000).
cd ~/workspace/lms || exit 1
RESULTS=/tmp/lms_all_suites_results.txt
: > "$RESULTS"
for suite in test_flows test_phase2 test_phase3 test_phase4 test_chat_fixes \
             test_phase5 test_phase6 test_phase7 test_phase8 test_phase9 \
             test_phase10 test_phase11 test_phase12 test_phase13_ai \
             test_phase13_auth test_phase13_learning test_phase13_money \
             test_phase13_parked test_phase13_social test_totp_crypto \
             test_ui14 test_ui15_overflow test_recorded_sessions test_lockdown \
             test_dashboard_sections test_live_classes_rework; do
  echo "##### $suite" | tee -a "$RESULTS"
  ./run_suite.sh "$suite" > "/tmp/run_${suite}.out" 2>&1
  RC=$?
  tail -3 "/tmp/run_${suite}.out" | tee -a "$RESULTS"
  echo "exit=$RC" | tee -a "$RESULTS"
  sleep 2
done
echo "##### DONE" | tee -a "$RESULTS"
