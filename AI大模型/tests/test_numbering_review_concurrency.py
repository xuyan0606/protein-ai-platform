import importlib.util
import tempfile
import threading
import time
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "serve_numbering_review_platform.py"
SPEC = importlib.util.spec_from_file_location("numbering_review_server", SCRIPT)
server = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(server)


class NumberingReviewConcurrencyTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.original_decisions = server.DECISIONS
        self.original_ledger = server.PIPELINE_JOB_LEDGER
        server.DECISIONS = Path(self.tempdir.name) / "numbering_curation_decisions.jsonl"
        server.PIPELINE_JOB_LEDGER = Path(self.tempdir.name) / "pipeline_jobs.jsonl"

    def tearDown(self):
        server.DECISIONS = self.original_decisions
        server.PIPELINE_JOB_LEDGER = self.original_ledger
        self.tempdir.cleanup()

    def test_concurrent_decisions_for_different_records_are_both_persisted(self):
        barrier = threading.Barrier(2)

        def save(record_id):
            barrier.wait()
            server.save_decision({"record_id": record_id, "decision": "keep_unresolved_weak"})

        threads = [threading.Thread(target=save, args=(record_id,)) for record_id in ("record-a", "record-b")]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertTrue(all(not thread.is_alive() for thread in threads))

        rows = server.load_jsonl(server.DECISIONS)
        self.assertEqual({"record-a", "record-b"}, {row["record_id"] for row in rows})

    def test_saved_decision_receives_a_submission_receipt(self):
        server.save_decision({"record_id": "record-a", "decision": "keep_unresolved_weak"})

        row = server.load_jsonl(server.DECISIONS)[0]
        self.assertTrue(row["submission_id"])
        self.assertTrue(row["submitted_at"].endswith("+00:00"))

    def test_stale_submission_for_the_same_record_is_rejected(self):
        first = server.save_decision({"record_id": "record-a", "decision": "keep_unresolved_weak"})
        server.save_decision({
            "record_id": "record-a",
            "decision": "reject_label",
            "expected_submission_id": first["submission_id"],
        })

        with self.assertRaisesRegex(ValueError, "decision_conflict"):
            server.save_decision({
                "record_id": "record-a",
                "decision": "map_to_canonical",
                "expected_submission_id": first["submission_id"],
            })

    def test_safe_pipeline_jobs_are_serialized_without_rejecting_the_second_submitter(self):
        original_run_step = server.run_step
        active = 0
        max_active = 0
        active_lock = threading.Lock()

        def slow_run(step):
            nonlocal active, max_active
            with active_lock:
                active += 1
                max_active = max(max_active, active)
            time.sleep(0.08)
            with active_lock:
                active -= 1
            return {"step": step, "command": "test", "returncode": 0, "ok": True, "stdout": "", "stderr": ""}

        server.run_step = slow_run
        try:
            first = server.start_run_step("safe_pipeline")
            second = server.start_run_step("safe_pipeline")
            self.assertEqual("queued", second["status"])
            self._wait_for_run(first["run_id"])
            self._wait_for_run(second["run_id"])
            self.assertEqual(1, max_active)
        finally:
            server.run_step = original_run_step

    def _wait_for_run(self, run_id):
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            run = server.get_run_status(run_id)
            if run and run["status"] in {"succeeded", "failed"}:
                self.assertEqual("succeeded", run["status"])
                return
            time.sleep(0.01)
        self.fail(f"timed out waiting for {run_id}")


if __name__ == "__main__":
    unittest.main()
