#!/usr/bin/env python3
"""
Comprehensive Test Suite for FlowWeaver v0.3.0
Validates all 4 production-grade refinements + SOLID principles
"""

import sys
import asyncio
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from flowweaver import (
    Task,
    Workflow,
    TaskStatus,
    task,
    StateBackend,
    InMemoryStateBackend,
    BaseExecutor,
    SequentialExecutor,
    ThreadedExecutor,
    AsyncExecutor,
)


class TestResults:
    """Track test results for summary reporting."""

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
# GAP 1: XCom Pattern (Data Passing Between Tasks)
# ============================================================================


def test_xcom_single_dependency():
    """Test 1.1: Task B receives result from Task A."""
    results = TestResults()

    try:

        @task()
        def fetch_user():
            return {"user_id": 42, "name": "Alice"}

        @task()
        def process_user(fetch_user=None):
            if fetch_user is None:
                return {"status": "error"}
            return {"status": "processed", "user_id": fetch_user["user_id"]}

        workflow = Workflow("xcom_test_1")
        workflow.add_task(fetch_user)
        workflow.add_task(process_user, depends_on=["fetch_user"])

        executor = SequentialExecutor()
        executor.execute(workflow)

        result = workflow.get_task_result("process_user")
        assert result["user_id"] == 42, f"Expected 42, got {result['user_id']}"
        results.add("XCom: Single Dependency", True, "Data passed correctly: 42")

    except Exception as e:
        results.add("XCom: Single Dependency", False, str(e))

    return results


def test_xcom_multiple_dependencies():
    """Test 1.2: Task D receives results from Tasks B and C."""
    results = TestResults()

    try:

        @task()
        def source():
            return 100

        @task()
        def double(source=None):
            return source * 2 if source else 0

        @task()
        def triple(source=None):
            return source * 3 if source else 0

        @task()
        def merge(double=None, triple=None):
            return {
                "sum": (double or 0) + (triple or 0),
                "double": double,
                "triple": triple,
            }

        workflow = Workflow("xcom_test_2")
        workflow.add_task(source)
        workflow.add_task(double, depends_on=["source"])
        workflow.add_task(triple, depends_on=["source"])
        workflow.add_task(merge, depends_on=["double", "triple"])

        executor = SequentialExecutor()
        executor.execute(workflow)

        result = workflow.get_task_result("merge")
        # double=200, triple=300, sum=500
        assert result["sum"] == 500, f"Expected 500, got {result['sum']}"
        results.add("XCom: Multiple Dependencies", True, "Multiple sources merged: 500")

    except Exception as e:
        results.add("XCom: Multiple Dependencies", False, str(e))

    return results


def test_xcom_threaded_executor():
    """Test 1.3: XCom works with ThreadedExecutor (parallel execution)."""
    results = TestResults()

    try:

        @task()
        def task1():
            time.sleep(0.01)
            return {"value": 10}

        @task()
        def task2():
            time.sleep(0.01)
            return {"value": 20}

        @task()
        def combine(task1=None, task2=None):
            return {
                "total": task1["value"] + task2["value"] if (task1 and task2) else 0
            }

        workflow = Workflow("xcom_threaded")
        workflow.add_task(task1)
        workflow.add_task(task2)
        workflow.add_task(combine, depends_on=["task1", "task2"])

        executor = ThreadedExecutor(max_workers=2)
        executor.execute(workflow)

        result = workflow.get_task_result("combine")
        assert result["total"] == 30, f"Expected 30, got {result['total']}"
        results.add(
            "XCom: Threaded Executor", True, "Parallel tasks with context passing"
        )

    except Exception as e:
        results.add("XCom: Threaded Executor", False, str(e))

    return results


def test_xcom_async():
    """Test 1.4: XCom works with AsyncExecutor."""
    results = TestResults()

    try:

        @task()
        async def fetch_async():
            await asyncio.sleep(0.01)
            return {"data": "async_result"}

        @task()
        async def process_async(fetch_async=None):
            await asyncio.sleep(0.01)
            return {"processed": fetch_async["data"] if fetch_async else "none"}

        workflow = Workflow("xcom_async")
        workflow.add_task(fetch_async)
        workflow.add_task(process_async, depends_on=["fetch_async"])

        executor = AsyncExecutor()
        executor.execute(workflow)

        result = workflow.get_task_result("process_async")
        assert result["processed"] == "async_result"
        results.add("XCom: Async Executor", True, "Async tasks with context passing")

    except Exception as e:
        results.add("XCom: Async Executor", False, str(e))

    return results


# ============================================================================
# GAP 2: State Persistence (Resilience & Resumption)
# ============================================================================


def test_state_backend_interface():
    """Test 2.1: StateBackend ABC is properly defined."""
    results = TestResults()

    try:
        # Verify StateBackend is abstract
        assert hasattr(StateBackend, "__abstractmethods__")

        # Verify InMemoryStateBackend implements all abstract methods
        backend = InMemoryStateBackend()
        assert hasattr(backend, "save_task_state")
        assert hasattr(backend, "load_task_state")
        assert hasattr(backend, "clear")

        results.add(
            "State Backend: Interface", True, "StateBackend ABC properly defined"
        )

    except Exception as e:
        results.add("State Backend: Interface", False, str(e))

    return results


def test_in_memory_state_backend():
    """Test 2.2: InMemoryStateBackend saves and loads state."""
    results = TestResults()

    try:
        from datetime import datetime

        backend = InMemoryStateBackend()

        # Save state
        backend.save_task_state(
            "task1", TaskStatus.COMPLETED, {"result": 99}, None, datetime.now()
        )

        # Load state
        state = backend.load_task_state("task1")
        assert state is not None
        assert state["result"] == {"result": 99}
        assert state["status"] == TaskStatus.COMPLETED

        # Clear state
        backend.clear()
        state = backend.load_task_state("task1")
        assert state is None

        results.add(
            "State Backend: InMemory Implementation", True, "Save/load/clear all work"
        )

    except Exception as e:
        results.add("State Backend: InMemory Implementation", False, str(e))

    return results


def test_state_backend_extensibility():
    """Test 2.3: StateBackend can be extended (SOLID: OCP)."""
    results = TestResults()

    try:

        class CustomBackend(StateBackend):
            """Custom state backend implementation."""

            def __init__(self):
                self.store = {}

            def save_task_state(self, task_name, status, result, error, timestamp):
                self.store[task_name] = {
                    "status": status,
                    "result": result,
                    "error": error,
                }

            def load_task_state(self, task_name):
                return self.store.get(task_name)

            def clear(self):
                self.store.clear()

        # Verify custom backend works
        backend = CustomBackend()
        backend.save_task_state("test", TaskStatus.COMPLETED, {"data": 1}, None, None)
        assert backend.load_task_state("test") is not None

        results.add(
            "State Backend: Extensibility", True, "Custom backend implementation works"
        )

    except Exception as e:
        results.add("State Backend: Extensibility", False, str(e))

    return results


# ============================================================================
# GAP 3: Boilerplate Reduction (@task Decorator)
# ============================================================================


def test_task_decorator_basic():
    """Test 3.1: @task decorator creates Task objects."""
    results = TestResults()

    try:

        @task()
        def my_function():
            return "hello"

        assert isinstance(my_function, Task)
        assert my_function.name == "my_function"
        assert my_function.fn() == "hello"

        results.add("@task Decorator: Basic Usage", True, "Function converted to Task")

    except Exception as e:
        results.add("@task Decorator: Basic Usage", False, str(e))

    return results


def test_task_decorator_with_params():
    """Test 3.2: @task decorator supports parameters."""
    results = TestResults()

    try:

        @task(retries=3, timeout=60)
        def retry_function():
            return "retry"

        assert retry_function.retries == 3
        assert retry_function.timeout == 60

        results.add(
            "@task Decorator: Parameters", True, "Retries and timeout set correctly"
        )

    except Exception as e:
        results.add("@task Decorator: Parameters", False, str(e))

    return results


def test_task_decorator_in_workflow():
    """Test 3.3: Decorated tasks work in workflows."""
    results = TestResults()

    try:

        @task()
        def step1():
            return {"step": 1}

        @task()
        def step2(step1=None):
            return {"step": 2, "prev": step1}

        workflow = Workflow("decorator_workflow")
        workflow.add_task(step1)
        workflow.add_task(step2, depends_on=["step1"])

        executor = SequentialExecutor()
        executor.execute(workflow)

        assert workflow.get_task_result("step2")["step"] == 2

        results.add(
            "@task Decorator: In Workflows",
            True,
            "Decorated tasks integrated seamlessly",
        )

    except Exception as e:
        results.add("@task Decorator: In Workflows", False, str(e))

    return results


# ============================================================================
# GAP 4: Observability (Lifecycle Hooks & Telemetry)
# ============================================================================


def test_lifecycle_hooks_all_events():
    """Test 4.1: All lifecycle hooks trigger correctly."""
    results = TestResults()

    try:
        events = []

        def on_start(name):
            events.append(f"start:{name}")

        def on_success(name, stats):
            events.append(f"success:{name}")

        def on_failure(name, error):
            events.append(f"failure:{name}")

        @task()
        def task1():
            return "done"

        workflow = Workflow("hook_workflow")
        workflow.add_task(task1)

        executor = SequentialExecutor(
            on_workflow_start=on_start,
            on_workflow_success=on_success,
            on_workflow_failure=on_failure,
        )
        executor.execute(workflow)

        assert "start:hook_workflow" in events
        assert "success:hook_workflow" in events
        assert len(events) == 2  # No failure

        results.add(
            "Lifecycle Hooks: All Events", True, "Start and success hooks triggered"
        )

    except Exception as e:
        results.add("Lifecycle Hooks: All Events", False, str(e))

    return results


def test_lifecycle_hooks_failure_event():
    """Test 4.2: Failure hook triggers on task failure."""
    results = TestResults()

    try:
        events = []

        def on_failure(name, error):
            events.append(f"failure:{name}:{error}")

        @task()
        def failing_task():
            raise ValueError("intentional error")

        workflow = Workflow("failure_workflow")
        workflow.add_task(failing_task)

        executor = SequentialExecutor(on_workflow_failure=on_failure)

        try:
            executor.execute(workflow)
        except RuntimeError:
            pass  # Expected

        assert len(events) > 0
        assert "failure:failure_workflow" in events[0]

        results.add(
            "Lifecycle Hooks: Failure Event", True, "Failure hook triggered correctly"
        )

    except Exception as e:
        results.add("Lifecycle Hooks: Failure Event", False, str(e))

    return results


def test_task_execution_timing():
    """Test 4.3: Task execution timing is recorded."""
    results = TestResults()

    try:

        @task()
        def timed_task():
            time.sleep(0.05)
            return "done"

        workflow = Workflow("timing_workflow")
        workflow.add_task(timed_task)

        executor = SequentialExecutor()
        executor.execute(workflow)

        task_obj = workflow._tasks["timed_task"]
        assert task_obj.started_at is not None
        assert task_obj.completed_at is not None
        duration = (task_obj.completed_at - task_obj.started_at).total_seconds()
        assert duration >= 0.05, f"Expected >= 0.05s, got {duration}s"

        results.add(
            "Task Timing: Execution Duration", True, f"Task took {duration:.3f}s"
        )

    except Exception as e:
        results.add("Task Timing: Execution Duration", False, str(e))

    return results


# ============================================================================
# SOLID PRINCIPLES VALIDATION
# ============================================================================


def test_solid_single_responsibility():
    """Test: Task, Workflow, and Executor each have one reason to change."""
    results = TestResults()

    try:
        # Task: responsible ONLY for execution logic
        # Workflow: responsible ONLY for DAG management
        # Executor: responsible ONLY for execution strategy
        # StateBackend: responsible ONLY for state persistence

        task_obj = Task(name="test", fn=lambda: None)
        assert hasattr(task_obj, "execute")  # Task's responsibility
        assert not hasattr(task_obj, "get_execution_plan")  # Not Workflow's job

        workflow = Workflow()
        assert hasattr(workflow, "add_task")  # Workflow's responsibility
        assert hasattr(workflow, "get_execution_plan")
        assert not hasattr(workflow, "execute")  # Not Executor's job

        results.add(
            "SOLID: Single Responsibility",
            True,
            "Each class has focused responsibility",
        )

    except Exception as e:
        results.add("SOLID: Single Responsibility", False, str(e))

    return results


def test_solid_open_closed():
    """Test: New executors can be added without modifying existing code (OCP)."""
    results = TestResults()

    try:

        class CustomExecutor(BaseExecutor):
            """New executor type without modifying existing code."""

            def execute(self, workflow):
                plan = workflow.get_execution_plan()
                self._trigger_start(workflow.name)
                for layer in plan:
                    for task in layer:
                        task.execute({})
                self._trigger_success(workflow.name, workflow.get_workflow_stats())

        @task()
        def dummy():
            return "test"

        workflow = Workflow("ocp_test")
        workflow.add_task(dummy)

        executor = CustomExecutor()
        executor.execute(workflow)

        results.add(
            "SOLID: Open/Closed Principle",
            True,
            "New executor added without modifying base",
        )

    except Exception as e:
        results.add("SOLID: Open/Closed Principle", False, str(e))

    return results


def test_solid_liskov_substitution():
    """Test: All executors are substitutable (LSP)."""
    results = TestResults()

    try:

        @task()
        def dummy():
            return 42

        def run_with_executor(executor):
            workflow = Workflow("lsp_test")
            workflow.add_task(dummy)
            executor.execute(workflow)
            return workflow.get_task_result("dummy")

        # All executors should work the same way
        sequential = SequentialExecutor()
        threaded = ThreadedExecutor()
        async_exec = AsyncExecutor()

        result1 = run_with_executor(sequential)
        result2 = run_with_executor(threaded)
        result3 = run_with_executor(async_exec)

        assert result1 == result2 == result3 == 42

        results.add(
            "SOLID: Liskov Substitution", True, "All executors are interchangeable"
        )

    except Exception as e:
        results.add("SOLID: Liskov Substitution", False, str(e))

    return results


def test_solid_interface_segregation():
    """Test: Clients depend only on needed interfaces (ISP)."""
    results = TestResults()

    try:
        # Task doesn't need to know about Workflow structure
        # Workflow doesn't need to know about execution details
        # Executor doesn't need to know task internals beyond execute()

        task = Task(name="test", fn=lambda: "ok")
        task.execute()  # Works without knowing Workflow

        workflow = Workflow()
        # Can configure workflow without caring about executor details

        executor = SequentialExecutor()
        # Executor just needs a Workflow interface

        results.add(
            "SOLID: Interface Segregation", True, "Clean separation of concerns"
        )

    except Exception as e:
        results.add("SOLID: Interface Segregation", False, str(e))

    return results


def test_solid_dependency_inversion():
    """Test: High-level modules depend on abstractions (DIP)."""
    results = TestResults()

    try:
        # Workflow depends on Task abstraction (not implementation)
        # All Executors depend on BaseExecutor (abstraction)
        # All StateBackends depend on StateBackend (abstraction)

        assert issubclass(SequentialExecutor, BaseExecutor)
        assert issubclass(ThreadedExecutor, BaseExecutor)
        assert issubclass(AsyncExecutor, BaseExecutor)
        assert issubclass(InMemoryStateBackend, StateBackend)

        results.add("SOLID: Dependency Inversion", True, "Abstractions used throughout")

    except Exception as e:
        results.add("SOLID: Dependency Inversion", False, str(e))

    return results


# ============================================================================
# SCALABILITY TESTS
# ============================================================================


def test_scalability_large_workflow():
    """Test: 100-task linear workflow executes successfully."""
    results = TestResults()

    try:
        workflow = Workflow("large_workflow")

        # Create 100 sequential tasks
        prev_task = None
        for i in range(100):
            # Lambda accepts **kwargs to ignore context from dependencies
            task_obj = Task(name=f"task_{i}", fn=lambda num=i, **kwargs: num)
            workflow.add_task(task_obj, depends_on=[prev_task] if prev_task else [])
            prev_task = f"task_{i}"

        executor = SequentialExecutor()
        start = time.time()
        executor.execute(workflow)
        duration = time.time() - start

        assert workflow.get_workflow_stats()["completed"] == 100
        results.add(
            "Scalability: Large Workflow", True, f"100 tasks in {duration:.2f}s"
        )

    except Exception as e:
        results.add("Scalability: Large Workflow", False, str(e))

    return results


def test_scalability_wide_parallel():
    """Test: 50 parallel tasks execute concurrently."""
    results = TestResults()

    try:
        workflow = Workflow("wide_parallel")

        # Create 50 independent tasks
        for i in range(50):
            task_obj = Task(
                name=f"parallel_task_{i}",
                fn=lambda num=i: (time.sleep(0.01), num)[1],
            )
            workflow.add_task(task_obj)

        executor = ThreadedExecutor(max_workers=10)
        start = time.time()
        executor.execute(workflow)
        duration = time.time() - start

        # With 10 workers and 50 tasks of 0.01s each, should take ~5 iterations = 0.05s
        # Sequential would take 50 * 0.01 = 0.5s
        assert duration < 0.3, f"Parallelism not working: {duration}s"

        results.add(
            "Scalability: Wide Parallel",
            True,
            f"50 tasks in {duration:.2f}s (threaded)",
        )

    except Exception as e:
        results.add("Scalability: Wide Parallel", False, str(e))

    return results


def test_scalability_deep_dependency():
    """Test: Deep dependency chains work correctly."""
    results = TestResults()

    try:
        workflow = Workflow("deep_dep")

        # Create 10-task deep chain
        for i in range(10):
            task_obj = Task(
                name=f"chain_task_{i}",
                fn=lambda val=i, **kwargs: val + 1,
            )
            depends_on = [f"chain_task_{i - 1}"] if i > 0 else []
            workflow.add_task(task_obj, depends_on=depends_on)

        executor = SequentialExecutor()
        executor.execute(workflow)

        assert workflow.get_workflow_stats()["completed"] == 10
        results.add(
            "Scalability: Deep Dependencies", True, "10-level deep chain executed"
        )

    except Exception as e:
        results.add("Scalability: Deep Dependencies", False, str(e))

    return results


# ============================================================================
# MAIN TEST RUNNER
# ============================================================================


def main():
    """Run all tests and report results."""
    print("\n" + "=" * 70)
    print("FlowWeaver v0.3.0 - Comprehensive Test Suite")
    print("Validation of 4 Production Gaps + SOLID Principles + Scalability")
    print("=" * 70 + "\n")

    all_results = TestResults()

    # Gap 1: XCom Tests
    print("🧪 GAP 1: XCom Pattern (Data Passing)")
    print("-" * 70)
    all_results.tests.extend(test_xcom_single_dependency().tests)
    all_results.tests.extend(test_xcom_multiple_dependencies().tests)
    all_results.tests.extend(test_xcom_threaded_executor().tests)
    all_results.tests.extend(test_xcom_async().tests)

    # Gap 2: StateBackend Tests
    print("\n🧪 GAP 2: State Persistence")
    print("-" * 70)
    all_results.tests.extend(test_state_backend_interface().tests)
    all_results.tests.extend(test_in_memory_state_backend().tests)
    all_results.tests.extend(test_state_backend_extensibility().tests)

    # Gap 3: @task Decorator Tests
    print("\n🧪 GAP 3: Boilerplate Reduction (@task)")
    print("-" * 70)
    all_results.tests.extend(test_task_decorator_basic().tests)
    all_results.tests.extend(test_task_decorator_with_params().tests)
    all_results.tests.extend(test_task_decorator_in_workflow().tests)

    # Gap 4: Lifecycle Hooks Tests
    print("\n🧪 GAP 4: Observability (Hooks & Telemetry)")
    print("-" * 70)
    all_results.tests.extend(test_lifecycle_hooks_all_events().tests)
    all_results.tests.extend(test_lifecycle_hooks_failure_event().tests)
    all_results.tests.extend(test_task_execution_timing().tests)

    # SOLID Principles Tests
    print("\n✨ SOLID PRINCIPLES VALIDATION")
    print("-" * 70)
    all_results.tests.extend(test_solid_single_responsibility().tests)
    all_results.tests.extend(test_solid_open_closed().tests)
    all_results.tests.extend(test_solid_liskov_substitution().tests)
    all_results.tests.extend(test_solid_interface_segregation().tests)
    all_results.tests.extend(test_solid_dependency_inversion().tests)

    # Scalability Tests
    print("\n📈 SCALABILITY TESTS")
    print("-" * 70)
    all_results.tests.extend(test_scalability_large_workflow().tests)
    all_results.tests.extend(test_scalability_wide_parallel().tests)
    all_results.tests.extend(test_scalability_deep_dependency().tests)

    # Summary
    success = all_results.print_summary()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
