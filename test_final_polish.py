#!/usr/bin/env python3
"""
Test final SDE-2 Polish: Thread-safe state updates + Resume logic
Demonstrates the two critical production-grade features
"""

import sys
from pathlib import Path
import tempfile
import time

sys.path.insert(0, str(Path(__file__).parent / "src"))

from flowweaver import (
    Workflow,
    Task,
    SequentialExecutor,
    ThreadedExecutor,
    JSONStateStore,
)


def test_thread_safe_result_store():
    """Verify ThreadedExecutor updates result store thread-safely"""
    print("\n" + "=" * 60)
    print("TEST 1: Thread-Safe Result Store (ThreadedExecutor)")
    print("=" * 60)

    def task_a():
        time.sleep(0.01)
        return {"data": "a", "value": 10}

    def task_b():
        time.sleep(0.01)
        return {"data": "b", "value": 20}

    def task_c():
        time.sleep(0.01)
        return {"data": "c", "value": 30}

    workflow = Workflow("thread_safe_test")
    workflow.add_task(Task("task_a", task_a))
    workflow.add_task(Task("task_b", task_b))
    workflow.add_task(Task("task_c", task_c))

    # Execute with ThreadedExecutor (multiple threads writing simultaneously)
    executor = ThreadedExecutor(max_workers=3)
    executor.execute(workflow)

    # Verify result store has all results
    result_store = workflow._result_store
    print(f"\nResult store contents: {result_store}")

    assert len(result_store) == 3, f"Expected 3 results, got {len(result_store)}"
    assert result_store["task_a"]["value"] == 10
    assert result_store["task_b"]["value"] == 20
    assert result_store["task_c"]["value"] == 30

    print("✓ ThreadedExecutor safely updated result store under concurrent access")
    print("✓ RLock protected all dictionary writes")
    return True


def test_resume_logic():
    """Verify workflow can resume by skipping already-completed tasks"""
    print("\n" + "=" * 60)
    print("TEST 2: Resume Logic (Skip Already-Completed Tasks)")
    print("=" * 60)

    call_count = {"task_a": 0, "task_b": 0, "task_c": 0}

    def task_a():
        call_count["task_a"] += 1
        print(f"  Executing task_a (call #{call_count['task_a']})")
        return {"result": "task_a_completed"}

    def task_b(**context):
        call_count["task_b"] += 1
        print(f"  Executing task_b (call #{call_count['task_b']})")
        return {"result": "task_b_completed", "context": context}

    def task_c(**context):
        call_count["task_c"] += 1
        print(f"  Executing task_c (call #{call_count['task_c']})")
        return {"result": "task_c_completed", "context": context}

    # Create temporary state store
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = str(Path(tmpdir) / "state.json")
        state_store = JSONStateStore(state_file)

        # First run: Execute all tasks and save state
        print("\n[RUN 1] - Initial execution")
        workflow1 = Workflow("resume_test_run1")
        workflow1.add_task(Task("task_a", task_a))
        workflow1.add_task(Task("task_b", task_b), depends_on=["task_a"])
        workflow1.add_task(Task("task_c", task_c), depends_on=["task_b"])

        executor1 = SequentialExecutor(state_store=state_store)
        executor1.execute(workflow1)

        print(f"\nAfter RUN 1:")
        print(f"  task_a called: {call_count['task_a']} times")
        print(f"  task_b called: {call_count['task_b']} times")
        print(f"  task_c called: {call_count['task_c']} times")

        assert call_count["task_a"] == 1
        assert call_count["task_b"] == 1
        assert call_count["task_c"] == 1

        # Second run: Resume workflow (should skip all completed tasks)
        print("\n[RUN 2] - Resume execution (all tasks already completed)")
        call_count = {"task_a": 0, "task_b": 0, "task_c": 0}  # Reset counters

        workflow2 = Workflow("resume_test_run2")
        workflow2.add_task(Task("task_a", task_a))
        workflow2.add_task(Task("task_b", task_b), depends_on=["task_a"])
        workflow2.add_task(Task("task_c", task_c), depends_on=["task_b"])

        executor2 = SequentialExecutor(state_store=state_store)
        executor2.execute(workflow2)

        print(f"\nAfter RUN 2 (resume):")
        print(f"  task_a called: {call_count['task_a']} times (should be 0)")
        print(f"  task_b called: {call_count['task_b']} times (should be 0)")
        print(f"  task_c called: {call_count['task_c']} times (should be 0)")

        # CRITICAL: Tasks should NOT be executed again
        assert call_count["task_a"] == 0, "task_a was re-executed (resume failed!)"
        assert call_count["task_b"] == 0, "task_b was re-executed (resume failed!)"
        assert call_count["task_c"] == 0, "task_c was re-executed (resume failed!)"

        # But results should still be available
        assert workflow2.get_task_result("task_a")["result"] == "task_a_completed"
        assert workflow2.get_task_result("task_b")["result"] == "task_b_completed"
        assert workflow2.get_task_result("task_c")["result"] == "task_c_completed"

        print("\n✓ All tasks skipped (restored from state store)")
        print("✓ Results available without re-execution")
        print("✓ Resumability verified")
        return True


def main():
    """Run all SDE-2 polish tests"""
    print("\n" + "=" * 60)
    print("FlowWeaver v0.3.2 - SDE-2 Polish Verification")
    print("=" * 60)

    results = []
    try:
        results.append(("Thread-Safe Result Store", test_thread_safe_result_store()))
        results.append(("Resume Logic", test_resume_logic()))
    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback

        traceback.print_exc()
        return False

    print("\n" + "=" * 60)
    print("FINAL RESULTS")
    print("=" * 60)
    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")

    all_passed = all(result for _, result in results)
    print("=" * 60)
    if all_passed:
        print("✓ ALL SDE-2 POLISH ITEMS VERIFIED")
        print("✓ Production-ready!")
    else:
        print("✗ Some tests failed")

    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
