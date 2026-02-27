#!/usr/bin/env python3
"""
Refinement Tests for FlowWeaver v0.3.1
Tests the enhanced features: thread-safe result store, JSONStateStore, SQLiteStateStore
"""

import sys
import asyncio
import time
import tempfile
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from flowweaver import (
    Task,
    Workflow,
    TaskStatus,
    task,
    SequentialExecutor,
    ThreadedExecutor,
    BaseStateStore,
    JSONStateStore,
    SQLiteStateStore,
)


class TestResults:
    """Track and report test results."""

    def __init__(self):
        self.tests = []
        self.passed = 0
        self.failed = 0

    def add(self, name: str, passed: bool, message: str = ""):
        self.tests.append({"name": name, "passed": passed, "message": message})
        if passed:
            self.passed += 1
        else:
            self.failed += 1

    def print_summary(self):
        print("\n" + "=" * 70)
        print(f"TEST RESULTS: {self.passed} passed, {self.failed} failed")
        print("=" * 70)
        for test in self.tests:
            status = "✅ PASS" if test["passed"] else "❌ FAIL"
            print(f"{status}: {test['name']}")
            if test["message"]:
                print(f"        {test['message']}")
        print("=" * 70)
        return self.failed == 0


# ============================================================================
# TEST 1: Thread-Safe Result Store (XCom Refinement)
# ============================================================================


def test_xcom_thread_safe_store():
    """Test: Workflow stores and retrieves results in thread-safe manner."""
    results = TestResults()

    try:

        @task()
        def compute_a():
            return 10

        @task()
        def compute_b(**kwargs):
            compute_a_val = kwargs.get("compute_a", 0)
            return compute_a_val * 2

        @task()
        def compute_c(**kwargs):
            compute_b_val = kwargs.get("compute_b", 0)
            return compute_b_val + 5

        workflow = Workflow("thread_safe_store")
        workflow.add_task(compute_a)
        workflow.add_task(compute_b, depends_on=["compute_a"])
        workflow.add_task(compute_c, depends_on=["compute_b"])

        executor = ThreadedExecutor(max_workers=3)
        executor.execute(workflow)

        # Check result store was populated
        assert workflow._result_store.get("compute_a") == 10
        assert workflow._result_store.get("compute_b") == 20
        assert workflow._result_store.get("compute_c") == 25

        results.add(
            "XCom: Thread-Safe Store",
            True,
            "All results properly stored and retrieved",
        )

    except Exception as e:
        results.add("XCom: Thread-Safe Store", False, str(e))

    return results


def test_xcom_context_building():
    """Test: Context is correctly built from dependent task results."""
    results = TestResults()

    try:
        workflow = Workflow("context_build")

        # Create tasks
        t1 = Task(name="source_a", fn=lambda: {"value": 100})
        t2 = Task(name="source_b", fn=lambda: {"multiplier": 2})
        t3 = Task(
            name="combine",
            fn=lambda source_a=None, source_b=None, **kwargs: (
                source_a["value"] * source_b["multiplier"]
            ),
        )

        workflow.add_task(t1)
        workflow.add_task(t2)
        workflow.add_task(t3, depends_on=["source_a", "source_b"])

        executor = SequentialExecutor()
        executor.execute(workflow)

        # Verify context was passed and used correctly
        result = workflow.get_task_result("combine")
        assert result == 200, f"Expected 200, got {result}"

        results.add(
            "XCom: Context Building",
            True,
            "Context correctly constructed from dependencies",
        )

    except Exception as e:
        results.add("XCom: Context Building", False, str(e))

    return results


# ============================================================================
# TEST 2: JSONStateStore Persistence
# ============================================================================


def test_json_state_store_save_load():
    """Test: JSONStateStore saves and loads task state correctly."""
    results = TestResults()

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "state.json"
            store = JSONStateStore(str(store_path))

            # Save state
            store.save_task_state(
                "task_1", TaskStatus.COMPLETED, result={"data": [1, 2, 3]}, error=None
            )

            # Load state
            loaded = store.load_task_state("task_1")
            assert loaded is not None
            assert loaded["status"] == TaskStatus.COMPLETED
            assert loaded["result"] == {"data": [1, 2, 3]}
            assert loaded["error"] is None

            results.add(
                "Storage: JSON Save/Load", True, "State saved and loaded correctly"
            )

    except Exception as e:
        results.add("Storage: JSON Save/Load", False, str(e))

    return results


def test_json_state_store_multiple_tasks():
    """Test: JSONStateStore handles multiple tasks correctly."""
    results = TestResults()

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "state.json"
            store = JSONStateStore(str(store_path))

            # Save multiple tasks
            for i in range(5):
                store.save_task_state(
                    f"task_{i}",
                    TaskStatus.COMPLETED,
                    result={"task_id": i},
                )

            # List and verify
            tasks = store.list_task_states()
            assert len(tasks) == 5, f"Expected 5 tasks, got {len(tasks)}"
            assert "task_0" in tasks
            assert "task_4" in tasks

            # Verify file structure
            with open(store_path, "r") as f:
                data = json.load(f)
                assert len(data) == 5
                assert data["task_2"]["result"]["task_id"] == 2

            results.add(
                "Storage: JSON Multi-Task", True, "Multiple tasks managed correctly"
            )

    except Exception as e:
        results.add("Storage: JSON Multi-Task", False, str(e))

    return results


def test_json_state_store_clear():
    """Test: JSONStateStore clear operations work correctly."""
    results = TestResults()

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "state.json"
            store = JSONStateStore(str(store_path))

            # Save and clear single task
            store.save_task_state("task_1", TaskStatus.COMPLETED, result="test")
            store.clear_task_state("task_1")
            assert store.load_task_state("task_1") is None

            # Save multiple and clear all
            for i in range(3):
                store.save_task_state(f"task_{i}", TaskStatus.COMPLETED)

            assert len(store.list_task_states()) == 3
            store.clear_all_states()
            assert len(store.list_task_states()) == 0

            results.add("Storage: JSON Clear", True, "Clear operations work correctly")

    except Exception as e:
        results.add("Storage: JSON Clear", False, str(e))

    return results


# ============================================================================
# TEST 3: SQLiteStateStore Persistence
# ============================================================================


def test_sqlite_state_store_save_load():
    """Test: SQLiteStateStore saves and loads task state correctly."""
    results = TestResults()

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "state.db"
            store = SQLiteStateStore(str(db_path))

            # Save state
            store.save_task_state(
                "task_1",
                TaskStatus.COMPLETED,
                result={"data": [1, 2, 3], "nested": {"key": "value"}},
                error=None,
            )

            # Load state
            loaded = store.load_task_state("task_1")
            assert loaded is not None
            assert loaded["status"] == TaskStatus.COMPLETED
            assert loaded["result"]["data"] == [1, 2, 3]
            assert loaded["result"]["nested"]["key"] == "value"

            results.add(
                "Storage: SQLite Save/Load", True, "State saved and loaded correctly"
            )

    except Exception as e:
        results.add("Storage: SQLite Save/Load", False, str(e))

    return results


def test_sqlite_state_store_scalability():
    """Test: SQLiteStateStore handles large number of tasks efficiently."""
    results = TestResults()

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "state.db"
            store = SQLiteStateStore(str(db_path))

            # Save 100 tasks
            start = time.time()
            for i in range(100):
                store.save_task_state(
                    f"task_{i:03d}",
                    TaskStatus.COMPLETED,
                    result={"index": i, "data": list(range(10))},
                )
            save_time = time.time() - start

            # Load all
            tasks = store.list_task_states()
            assert len(tasks) == 100

            # Spot check
            loaded = store.load_task_state("task_050")
            assert loaded["result"]["index"] == 50

            results.add(
                "Storage: SQLite Scalability",
                True,
                f"Saved 100 tasks in {save_time:.2f}s",
            )

    except Exception as e:
        results.add("Storage: SQLite Scalability", False, str(e))

    return results


# ============================================================================
# TEST 4: Integration - Workflow + JSONStateStore
# ============================================================================


def test_workflow_with_json_state_store():
    """Test: Workflow integrates with JSONStateStore for persistence."""
    results = TestResults()

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "workflow_state.json"
            store = JSONStateStore(str(store_path))

            # Execute workflow
            @task()
            def fetch():
                return {"user_id": 42, "name": "Alice"}

            @task()
            def process(fetch=None):
                return {"user_id": fetch["user_id"], "processed": True}

            workflow = Workflow("integration_test")
            workflow.add_task(fetch)
            workflow.add_task(process, depends_on=["fetch"])

            executor = SequentialExecutor()
            executor.execute(workflow)

            # Save to store
            for task_name in ["fetch", "process"]:
                task_obj = workflow.get_task(task_name)
                store.save_task_state(
                    task_name,
                    task_obj.status,
                    result=task_obj.result,
                    error=task_obj.error,
                )

            # Verify persistence
            assert store.load_task_state("fetch")["result"]["user_id"] == 42
            assert store.load_task_state("process")["result"]["processed"] is True

            results.add(
                "Integration: Workflow + JSON Store",
                True,
                "Workflow results persisted to JSON",
            )

    except Exception as e:
        results.add("Integration: Workflow + JSON Store", False, str(e))

    return results


def test_workflow_with_sqlite_state_store():
    """Test: Workflow integrates with SQLiteStateStore for persistence."""
    results = TestResults()

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "workflow_state.db"
            store = SQLiteStateStore(str(db_path))

            # Execute workflow
            @task()
            def transform():
                return [1, 2, 3, 4, 5]

            @task()
            def aggregate(transform=None):
                return {"sum": sum(transform), "count": len(transform)}

            workflow = Workflow("sqlite_integration")
            workflow.add_task(transform)
            workflow.add_task(aggregate, depends_on=["transform"])

            executor = SequentialExecutor()
            executor.execute(workflow)

            # Save to store
            for task_name in ["transform", "aggregate"]:
                task_obj = workflow.get_task(task_name)
                store.save_task_state(
                    task_name,
                    task_obj.status,
                    result=task_obj.result,
                    error=task_obj.error,
                )

            # Verify persistence and query
            agg_state = store.load_task_state("aggregate")
            assert agg_state["result"]["sum"] == 15
            assert agg_state["result"]["count"] == 5

            results.add(
                "Integration: Workflow + SQLite Store",
                True,
                "Workflow results persisted to SQLite",
            )

    except Exception as e:
        results.add("Integration: Workflow + SQLite Store", False, str(e))

    return results


# ============================================================================
# TEST 5: StateStore Abstract Interface
# ============================================================================


def test_state_store_interface():
    """Test: BaseStateStore ABC enforces required methods."""
    results = TestResults()

    try:
        # Verify JSONStateStore and SQLiteStateStore are proper implementations
        json_store = JSONStateStore()
        sqlite_store = SQLiteStateStore()

        # Both should have required methods
        assert callable(getattr(json_store, "save_task_state"))
        assert callable(getattr(json_store, "load_task_state"))
        assert callable(getattr(json_store, "clear_task_state"))
        assert callable(getattr(json_store, "clear_all_states"))
        assert callable(getattr(json_store, "list_task_states"))

        assert callable(getattr(sqlite_store, "save_task_state"))
        assert callable(getattr(sqlite_store, "load_task_state"))
        assert callable(getattr(sqlite_store, "clear_task_state"))
        assert callable(getattr(sqlite_store, "clear_all_states"))
        assert callable(getattr(sqlite_store, "list_task_states"))

        # Both should be instances of BaseStateStore
        assert isinstance(json_store, BaseStateStore)
        assert isinstance(sqlite_store, BaseStateStore)

        results.add(
            "Storage: Interface Compliance",
            True,
            "All implementations comply with BaseStateStore ABC",
        )

    except Exception as e:
        results.add("Storage: Interface Compliance", False, str(e))

    return results


# ============================================================================
# MAIN TEST RUNNER
# ============================================================================


def main():
    """Run all refinement tests."""
    print("\n" + "=" * 70)
    print("FlowWeaver v0.3.1 - Refinement Tests")
    print("Thread-Safe Store, JSONStateStore, SQLiteStateStore")
    print("=" * 70 + "\n")

    all_results = TestResults()

    # XCom Refinement Tests
    print("🧪 REFINEMENT 1: Thread-Safe Result Store (XCom)")
    print("-" * 70)
    all_results.tests.extend(test_xcom_thread_safe_store().tests)
    all_results.tests.extend(test_xcom_context_building().tests)

    # JSONStateStore Tests
    print("\n🧪 REFINEMENT 2: JSONStateStore Persistence")
    print("-" * 70)
    all_results.tests.extend(test_json_state_store_save_load().tests)
    all_results.tests.extend(test_json_state_store_multiple_tasks().tests)
    all_results.tests.extend(test_json_state_store_clear().tests)

    # SQLiteStateStore Tests
    print("\n🧪 REFINEMENT 3: SQLiteStateStore Persistence")
    print("-" * 70)
    all_results.tests.extend(test_sqlite_state_store_save_load().tests)
    all_results.tests.extend(test_sqlite_state_store_scalability().tests)

    # Integration Tests
    print("\n🧪 REFINEMENT 4: Integration Tests")
    print("-" * 70)
    all_results.tests.extend(test_workflow_with_json_state_store().tests)
    all_results.tests.extend(test_workflow_with_sqlite_state_store().tests)

    # Interface Tests
    print("\n🧪 REFINEMENT 5: StateStore Interface")
    print("-" * 70)
    all_results.tests.extend(test_state_store_interface().tests)

    # Summary
    success = all_results.print_summary()

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
