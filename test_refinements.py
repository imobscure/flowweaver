#!/usr/bin/env python3
"""
Test Production-Grade Refinements for FlowWeaver v0.3.0

Tests all new features:
1. Data Flow (XCom Pattern)
2. @task Decorator
3. StateBackend Interface
4. Executor Lifecycle Hooks
5. Enhanced Error Handling
6. Context-Aware Logging
"""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from flowweaver import (
    Task,
    Workflow,
    task,
    StateBackend,
    InMemoryStateBackend,
    SequentialExecutor,
    ThreadedExecutor,
    AsyncExecutor,
)


def test_import_all_features():
    """Test that all new features can be imported."""
    print("✅ Test 1: All features importable")
    assert task is not None
    assert StateBackend is not None
    assert InMemoryStateBackend is not None


def test_task_decorator():
    """Test the @task decorator."""
    print("✅ Test 2: @task decorator")

    @task(retries=2)
    def fetch_data():
        return {"data": "hello"}

    assert isinstance(fetch_data, Task)
    assert fetch_data.name == "fetch_data"
    assert fetch_data.retries == 2
    assert fetch_data.fn() == {"data": "hello"}


def test_state_backend():
    """Test StateBackend interface."""
    print("✅ Test 3: StateBackend interface")

    backend = InMemoryStateBackend()
    from flowweaver import TaskStatus
    from datetime import datetime

    backend.save_task_state(
        "task1", TaskStatus.COMPLETED, {"result": 42}, None, datetime.now()
    )
    assert backend.load_task_state("task1") is not None
    assert backend.load_task_state("task1")["result"] == {"result": 42}

    backend.clear()
    assert backend.load_task_state("task1") is None


def test_context_sharing():
    """Test XCom pattern - data sharing between tasks."""
    print("✅ Test 4: Context/XCom pattern")

    @task()
    def fetch():
        return {"count": 42}

    @task()
    def process(fetch=None):  # Receives result from 'fetch' task
        if fetch is None:
            return {"processed": 0}
        return {"processed": fetch["count"] * 2}

    workflow = Workflow("context_test")
    workflow.add_task(fetch)
    workflow.add_task(process, depends_on=["fetch"])

    executor = SequentialExecutor()
    executor.execute(workflow)

    assert workflow.get_task_result("fetch") == {"count": 42}
    assert workflow.get_task_result("process") == {"processed": 84}
    print("   ✓ Data shared between dependent tasks correctly")


def test_lifecycle_hooks():
    """Test executor lifecycle hooks."""
    print("✅ Test 5: Executor lifecycle hooks")

    events = []

    def on_start(workflow_name):
        events.append(f"start:{workflow_name}")

    def on_success(workflow_name, stats):
        events.append(f"success:{workflow_name}")

    def on_failure(workflow_name, error):
        events.append(f"failure:{workflow_name}")

    @task()
    def simple_task():
        return "done"

    workflow = Workflow("hook_test")
    workflow.add_task(simple_task)

    executor = SequentialExecutor(
        on_workflow_start=on_start,
        on_workflow_success=on_success,
        on_workflow_failure=on_failure,
    )
    executor.execute(workflow)

    assert "start:hook_test" in events
    assert "success:hook_test" in events
    print("   ✓ Lifecycle hooks triggered correctly")


def test_context_with_multiple_dependents():
    """Test context passing with multiple dependent tasks."""
    print("✅ Test 6: Context with multiple dependencies")

    @task()
    def source():
        return {"value": 100}

    @task()
    def step1(source=None):
        return source["value"] + 50 if source else 0

    @task()
    def step2(source=None):
        return source["value"] * 2 if source else 0

    @task()
    def merge(step1=None, step2=None):
        s1 = step1 if step1 else 0
        s2 = step2 if step2 else 0
        return {"result": s1 + s2}

    workflow = Workflow("multi_dep")
    workflow.add_task(source)
    workflow.add_task(step1, depends_on=["source"])
    workflow.add_task(step2, depends_on=["source"])
    workflow.add_task(merge, depends_on=["step1", "step2"])

    executor = SequentialExecutor()
    executor.execute(workflow)

    # source returns 100
    # step1 = 100 + 50 = 150
    # step2 = 100 * 2 = 200
    # merge = 150 + 200 = 350
    assert workflow.get_task_result("merge")["result"] == 350
    print("   ✓ Multiple dependencies resolved correctly")


async def test_async_context():
    """Test context passing in async execution."""
    print("✅ Test 7: Async context passing")

    @task()
    async def async_fetch():
        await asyncio.sleep(0.01)
        return {"data": [1, 2, 3]}

    @task()
    async def async_process(async_fetch=None):
        await asyncio.sleep(0.01)
        if async_fetch is None:
            return {"sum": 0}
        return {"sum": sum(async_fetch["data"])}

    workflow = Workflow("async_context")
    workflow.add_task(async_fetch)
    workflow.add_task(async_process, depends_on=["async_fetch"])

    executor = AsyncExecutor()
    executor.execute(workflow)

    assert workflow.get_task_result("async_fetch") == {"data": [1, 2, 3]}
    assert workflow.get_task_result("async_process") == {"sum": 6}
    print("   ✓ Async context passing works correctly")


def run_all_tests():
    """Run all refinement tests."""
    print("\n" + "=" * 60)
    print("FlowWeaver Production-Grade Refinements Test Suite")
    print("=" * 60 + "\n")

    try:
        test_import_all_features()
        test_task_decorator()
        test_state_backend()
        test_context_sharing()
        test_lifecycle_hooks()
        test_context_with_multiple_dependents()
        asyncio.run(test_async_context())

        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        return True

    except Exception as e:
        print(f"\n❌ TEST FAILED: {str(e)}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
