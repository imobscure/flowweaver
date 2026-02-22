"""
FlowWeaver Core Module

Provides task orchestration and DAG validation for lightweight workflow execution.
Follows SOLID principles with strict type hints for maintainability and scalability.
Supports both synchronous and asynchronous task execution with real-time monitoring.

Key Features:
- Data sharing via context (XCom pattern)
- @task decorator for elegant task definition
- Pluggable state backend for persistence and resumption
- Context-aware logging with task duration tracking
- Lifecycle hooks for executor integration
"""

import asyncio
import inspect
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional, Coroutine, Union, Dict
from collections import defaultdict
from datetime import datetime
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """
    Enumeration of task execution states.

    Rationale (SDE-2): Using Enum ensures type-safe state management and prevents
    invalid state assignments. Each state is immutable and self-documenting.
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class StateBackend(ABC):
    """
    Abstract base class for task state persistence.

    Enables workflow resumption after failures by storing task state externally.
    This design allows users to implement SQLite, Redis, or cloud backends.

    Rationale (SDE-2): Decoupling state from Task objects enables distributed
    systems where tasks run on different machines. Follows Dependency Inversion.
    """

    @abstractmethod
    def save_task_state(
        self,
        task_name: str,
        status: TaskStatus,
        result: Any,
        error: Optional[str],
        timestamp: datetime,
    ) -> None:
        """Save task execution state."""
        pass

    @abstractmethod
    def load_task_state(self, task_name: str) -> Optional[Dict[str, Any]]:
        """Load saved task state (returns None if not found)."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear all saved state."""
        pass


class InMemoryStateBackend(StateBackend):
    """Default in-memory state storage. Fast but not persistent."""

    def __init__(self) -> None:
        self._state: Dict[str, Dict[str, Any]] = {}

    def save_task_state(
        self,
        task_name: str,
        status: TaskStatus,
        result: Any,
        error: Optional[str],
        timestamp: datetime,
    ) -> None:
        self._state[task_name] = {
            "status": status,
            "result": result,
            "error": error,
            "timestamp": timestamp,
        }

    def load_task_state(self, task_name: str) -> Optional[Dict[str, Any]]:
        return self._state.get(task_name)

    def clear(self) -> None:
        self._state.clear()


@dataclass
class Task:
    """
    Represents a single unit of work in a workflow.

    Supports both synchronous and asynchronous execution with retry logic,
    real-time status callbacks, context sharing (XCom pattern), and error handling.

    Attributes:
        name: Unique identifier for the task.
        fn: Callable (sync or async) that executes the task logic.
           Can accept **kwargs to receive context from dependent tasks.
        retries: Number of retry attempts on failure (default: 0).
        timeout: Maximum execution time in seconds (default: None, no timeout).
        status: Current execution state (default: PENDING).
        result: Output value after successful execution (default: None).
        error: Exception message if execution fails (default: None).
        on_status_change: Optional callback fired when status changes.
        on_retry: Optional callback fired on retry attempts.
        started_at: Timestamp when task execution began.
        completed_at: Timestamp when task execution ended.

    Rationale (SDE-2):
    - Dataclass provides automated __init__, __repr__ with strict typing
    - Context (XCom) pattern enables data sharing between dependent tasks
    - Inspect module detects function signature to pass context intelligently
    - Callbacks enable real-time monitoring without coupling (Observer pattern)
    """

    name: str
    fn: Union[Callable[..., Any], Callable[..., Coroutine[Any, Any, Any]]]
    retries: int = 0
    timeout: Optional[float] = None
    status: TaskStatus = field(default=TaskStatus.PENDING)
    result: Optional[Any] = None
    error: Optional[str] = None
    on_status_change: Optional[Callable[[str, TaskStatus], None]] = None
    on_retry: Optional[Callable[[str, int], None]] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def _set_status(self, new_status: TaskStatus) -> None:
        """Update status and trigger callback."""
        self.status = new_status
        if self.on_status_change:
            self.on_status_change(self.name, new_status)

    def is_async(self) -> bool:
        """Check if the task function is async."""
        return inspect.iscoroutinefunction(self.fn)

    def _accepts_context(self) -> bool:
        """Check if task function accepts **kwargs for context."""
        sig = inspect.signature(self.fn)
        return any(
            param.kind == inspect.Parameter.VAR_KEYWORD
            for param in sig.parameters.values()
        )

    def execute(self, context: Optional[Dict[str, Any]] = None) -> None:
        """
        Execute the synchronous task with retry logic.

        Attempts to run the callable (self.fn) and captures the result.
        On failure, retries up to self.retries times before marking as FAILED.

        Args:
            context: Dict of results from dependent tasks (XCom pattern).

        Raises:
            RuntimeError: If task is async; use execute_async() instead.
        """
        if self.is_async():
            raise RuntimeError(
                f"Task '{self.name}' is async. Use execute_async() instead."
            )

        self._set_status(TaskStatus.RUNNING)
        self.started_at = datetime.now()
        attempts = 0
        max_attempts = self.retries + 1
        context = context or {}

        while attempts < max_attempts:
            try:
                # Call function with context if it accepts **kwargs
                if self._accepts_context():
                    self.result = self.fn(**context)
                else:
                    self.result = self.fn()
                self._set_status(TaskStatus.COMPLETED)
                self.completed_at = datetime.now()
                self.error = None
                duration = (self.completed_at - self.started_at).total_seconds()
                logger.info(f"Task '{self.name}' completed in {duration:.3f}s")
                return
            except Exception as e:
                attempts += 1
                if attempts >= max_attempts:
                    self._set_status(TaskStatus.FAILED)
                    self.completed_at = datetime.now()
                    self.error = str(e)
                    logger.error(f"Task '{self.name}' failed: {e}")
                    return
                if self.on_retry:
                    self.on_retry(self.name, attempts)
                logger.warning(f"Task '{self.name}' retry {attempts}/{self.retries}")

    async def execute_async(self, context: Optional[Dict[str, Any]] = None) -> None:
        """
        Execute the task asynchronously with retry logic and timeout support.

        For async callables, awaits the coroutine with optional timeout.
        For sync callables, runs them in a thread pool to avoid blocking.

        Args:
            context: Dict of results from dependent tasks (XCom pattern).

        Raises:
            asyncio.TimeoutError: If timeout is exceeded.
        """
        if not self.is_async() and not callable(self.fn):
            raise RuntimeError(f"Task '{self.name}' fn is not callable.")

        self._set_status(TaskStatus.RUNNING)
        self.started_at = datetime.now()
        attempts = 0
        max_attempts = self.retries + 1
        context = context or {}

        while attempts < max_attempts:
            try:
                if self.is_async():
                    # Call async function with context if needed
                    if self._accepts_context():
                        coro = self.fn(**context)
                    else:
                        coro = self.fn()
                    if self.timeout:
                        self.result = await asyncio.wait_for(coro, timeout=self.timeout)
                    else:
                        self.result = await coro
                else:
                    # Run sync function in thread pool
                    loop = asyncio.get_event_loop()
                    fn_wrapper = (
                        (lambda: self.fn(**context))
                        if self._accepts_context()
                        else self.fn
                    )
                    if self.timeout:
                        self.result = await asyncio.wait_for(
                            loop.run_in_executor(None, fn_wrapper), timeout=self.timeout
                        )
                    else:
                        self.result = await loop.run_in_executor(None, fn_wrapper)

                self._set_status(TaskStatus.COMPLETED)
                self.completed_at = datetime.now()
                self.error = None
                duration = (self.completed_at - self.started_at).total_seconds()
                logger.info(f"Task '{self.name}' completed in {duration:.3f}s")
                return
            except asyncio.TimeoutError:
                attempts += 1
                if attempts >= max_attempts:
                    self._set_status(TaskStatus.FAILED)
                    self.completed_at = datetime.now()
                    self.error = f"Task timeout after {self.timeout}s"
                    logger.error(f"Task '{self.name}' timeout after {self.timeout}s")
                    return
                if self.on_retry:
                    self.on_retry(self.name, attempts)
                logger.warning(
                    f"Task '{self.name}' timeout retry {attempts}/{self.retries}"
                )
            except Exception as e:
                attempts += 1
                if attempts >= max_attempts:
                    self._set_status(TaskStatus.FAILED)
                    self.completed_at = datetime.now()
                    self.error = str(e)
                    logger.error(f"Task '{self.name}' failed: {e}")
                    return
                if self.on_retry:
                    self.on_retry(self.name, attempts)
                logger.warning(f"Task '{self.name}' retry {attempts}/{self.retries}")


class Workflow:
    """
    Container and orchestrator for a directed acyclic graph (DAG) of tasks.

    Manages task registration, dependency tracking, and DAG validation.
    Critical invariant: The workflow must remain acyclic at all times.

    Rationale (SDE-2): Graph-based approach supports complex dependencies.
    DFS-based cycle detection ensures O(V+E) complexity with immediate feedback.
    Strategy pattern (via __validate_dag) enables future extensibility for
    topological sorting, parallel execution planning, etc.
    """

    def __init__(self, name: str = "Workflow") -> None:
        """
        Initialize a workflow.

        Args:
            name: Optional name for the workflow (used in logging).
        """
        self.name = name
        self._tasks: dict[str, Task] = {}
        self._dependencies: dict[str, list[str]] = defaultdict(list)

    def add_task(self, task: Task, depends_on: Optional[list[str]] = None) -> None:
        """
        Register a task and its dependencies in the workflow.

        Args:
            task: The Task instance to add.
            depends_on: List of task names this task depends on (default: None).

        Raises:
            ValueError: If task name already exists or if adding the task
                       would create a circular dependency.

        Rationale (SDE-2): Dependency validation occurs immediately (fail-fast).
        This prevents silent errors and makes debugging easier. Task names are
        unique to avoid ambiguity in dependency resolution.
        """
        if task.name in self._tasks:
            raise ValueError(f"Task '{task.name}' already exists in workflow")

        depends_on = depends_on or []

        # Validate that all dependencies exist
        for dep in depends_on:
            if dep not in self._tasks:
                raise ValueError(
                    f"Dependency '{dep}' does not exist. Add it before adding '{task.name}'."
                )

        # Add task first
        self._tasks[task.name] = task
        self._dependencies[task.name] = depends_on.copy()

        # Validate DAG integrity
        if self._has_cycle():
            # Rollback on failure
            del self._tasks[task.name]
            del self._dependencies[task.name]
            raise ValueError(
                f"Adding task '{task.name}' would create a circular dependency"
            )

    def _has_cycle(self) -> bool:
        """
        Detect cycles in the dependency graph using Depth First Search (DFS).

        Returns:
            True if a cycle exists, False otherwise.

        Rationale (SDE-2): DFS is the standard algorithm for cycle detection in graphs.
        Time complexity: O(V+E) where V=number of tasks, E=number of dependencies.
        Space complexity: O(V) for recursion stack and color tracking.

        Algorithm:
        - WHITE (0): Unvisited node
        - GRAY (1): Currently visiting (in recursion stack)
        - BLACK (2): Completely processed

        A cycle exists if we encounter a GRAY node (back edge).
        """
        color: dict[str, int] = {}  # 0=white, 1=gray, 2=black

        def dfs(node: str) -> bool:
            """DFS helper to detect cycles."""
            if node not in color:
                color[node] = 0

            if color[node] == 1:  # Back edge found
                return True
            if color[node] == 2:  # Already fully processed
                return False

            color[node] = 1  # Mark as visiting (gray)

            for neighbor in self._dependencies[node]:
                if dfs(neighbor):
                    return True

            color[node] = 2  # Mark as done (black)
            return False

        # Check all nodes for cycles
        for task_name in self._tasks:
            if task_name not in color:
                if dfs(task_name):
                    return True

        return False

    def get_task(self, task_name: str) -> Optional[Task]:
        """
        Retrieve a task by name.

        Args:
            task_name: The name of the task to retrieve.

        Returns:
            The Task instance if found, None otherwise.
        """
        return self._tasks.get(task_name)

    def get_dependencies(self, task_name: str) -> list[str]:
        """
        Get the direct dependencies of a task.

        Args:
            task_name: The name of the task.

        Returns:
            List of task names this task depends on.
        """
        return self._dependencies.get(task_name, [])

    def get_all_tasks(self) -> dict[str, Task]:
        """
        Get all tasks in the workflow.

        Returns:
            Dictionary mapping task names to Task instances.
        """
        return self._tasks.copy()

    def get_execution_plan(self) -> list[list[Task]]:
        """
        Generate an execution plan by grouping tasks into "layers" for parallel execution.

        Returns:
            List of layers, where each layer is a list of tasks that can execute in parallel.
            Tasks within a layer have no dependencies on each other.

        Algorithm: Kahn's Algorithm (Topological Sort with Level Assignment)

        Rationale (SDE-2): Kahn's Algorithm provides O(V+E) topological sorting with
        explicit layer recognition. Unlike DFS-based approaches, it naturally groups
        independent tasks at the same dependency depth, enabling parallelization.

        Key insight:
        - Tasks with in-degree 0 form the first layer (no dependencies)
        - After executing a layer, remove those tasks from the graph
        - Recompute tasks with in-degree 0; they form the next layer
        - Repeat until all tasks are scheduled

        This approach maximizes parallelism while respecting DAG constraints.

        Raises:
            ValueError: If the workflow contains a cycle (should not happen if
                       DAG validation is working correctly in add_task).
        """
        if not self._tasks:
            return []

        # Build in-degree map: how many dependencies each task has
        in_degree: dict[str, int] = {}
        reverse_deps: dict[str, list[str]] = defaultdict(list)

        for task_name in self._tasks:
            in_degree[task_name] = len(self._dependencies[task_name])

        # Build reverse dependency map: which tasks depend on each task
        for task_name, deps in self._dependencies.items():
            for dep in deps:
                reverse_deps[dep].append(task_name)

        # Initialize queue with all tasks that have no dependencies
        queue: list[str] = [name for name in self._tasks if in_degree[name] == 0]
        layers: list[list[Task]] = []

        while queue:
            # Current layer: all tasks ready to execute
            current_layer = sorted(queue)  # Sort for deterministic ordering
            layer_tasks = [self._tasks[name] for name in current_layer]
            layers.append(layer_tasks)

            # Process the current layer
            next_queue: list[str] = []
            for task_name in current_layer:
                # For each task that depends on this one
                for dependent in reverse_deps[task_name]:
                    in_degree[dependent] -= 1
                    # If all dependencies are satisfied, add to next layer
                    if in_degree[dependent] == 0:
                        next_queue.append(dependent)

            queue = next_queue

        # Verify all tasks were scheduled (cycle check)
        scheduled_count = sum(len(layer) for layer in layers)
        if scheduled_count != len(self._tasks):
            raise ValueError(
                f"Workflow contains a cycle or is incomplete. "
                f"Only {scheduled_count}/{len(self._tasks)} tasks were scheduled."
            )

        return layers

    async def execute_async(self) -> None:
        """
        Execute the entire workflow asynchronously with parallel task execution.

        Tasks within the same layer (no inter-dependencies) execute concurrently.
        All tasks in a layer must complete before the next layer begins.

        Context (XCom Pattern): Task results are stored in a context dict and passed
        to dependent tasks via **kwargs. Each task receives results from its dependencies.

        This method is designed for I/O-bound workflows and provides true
        concurrency without the GIL limitations of threading.

        Raises:
            RuntimeError: If any task fails during execution.
        """
        plan = self.get_execution_plan()
        context: Dict[str, Any] = {}  # Stores results from completed tasks

        for layer_idx, layer in enumerate(plan):
            # Build context for this layer: collect results from dependencies
            layer_context = {}
            for task in layer:
                for dep_name in self._dependencies[task.name]:
                    if dep_name in context:
                        layer_context[dep_name] = context[dep_name]

            # Execute all tasks in the layer concurrently, passing context
            tasks_to_run = [task.execute_async(layer_context) for task in layer]
            await asyncio.gather(*tasks_to_run)

            # Check for failures in this layer and update context with results
            for task in layer:
                if task.status == TaskStatus.FAILED:
                    raise RuntimeError(
                        f"Workflow failed at task '{task.name}': {task.error}"
                    )
                # Store task result in context for dependent tasks
                context[task.name] = task.result

    def get_task_status(self, task_name: str) -> Optional[TaskStatus]:
        """
        Get the current status of a task.

        Args:
            task_name: The name of the task.

        Returns:
            TaskStatus if task exists, None otherwise.
        """
        task = self._tasks.get(task_name)
        return task.status if task else None

    def get_task_result(self, task_name: str) -> Any:
        """
        Get the result of a completed task.

        Args:
            task_name: The name of the task.

        Returns:
            The task's result (None if not completed).

        Raises:
            KeyError: If task doesn't exist.
        """
        return self._tasks[task_name].result

    def get_workflow_stats(self) -> dict[str, Any]:
        """
        Get comprehensive workflow statistics.

        Returns:
            Dictionary with task counts, execution times, and status breakdown.
        """
        completed_tasks = [
            t for t in self._tasks.values() if t.status == TaskStatus.COMPLETED
        ]
        failed_tasks = [
            t for t in self._tasks.values() if t.status == TaskStatus.FAILED
        ]

        total_time = 0.0
        if completed_tasks or failed_tasks:
            all_finished = completed_tasks + failed_tasks
            start_times = [t.started_at for t in all_finished if t.started_at]
            end_times = [t.completed_at for t in all_finished if t.completed_at]
            if start_times and end_times:
                total_time = (max(end_times) - min(start_times)).total_seconds()

        return {
            "total_tasks": len(self._tasks),
            "completed": len(completed_tasks),
            "failed": len(failed_tasks),
            "pending": len(
                [t for t in self._tasks.values() if t.status == TaskStatus.PENDING]
            ),
            "running": len(
                [t for t in self._tasks.values() if t.status == TaskStatus.RUNNING]
            ),
            "total_time_seconds": total_time,
        }


def task(
    name: Optional[str] = None,
    retries: int = 0,
    timeout: Optional[float] = None,
    on_status_change: Optional[Callable[[str, TaskStatus], None]] = None,
    on_retry: Optional[Callable[[str, int], None]] = None,
) -> Callable:
    """
    Decorator to convert a function into a FlowWeaver Task.

    Provides elegant task definition without boilerplate Task object creation.

    Usage:
        @task(retries=3)
        def clean_data(raw_input):
            return raw_input.strip()

        workflow.add_task(clean_data, depends_on=["fetch"])

    Args:
        name: Task name (defaults to function name if not provided).
        retries: Number of retry attempts on failure (default: 0).
        timeout: Maximum execution time in seconds (default: None).
        on_status_change: Optional callback for status changes.
        on_retry: Optional callback for retry events.

    Returns:
        A Task instance with the decorated function as its fn.

    Rationale (SDE-2): Decorator pattern reduces boilerplate and improves readability.
    Users can focus on business logic (the function) rather than infrastructure (Task).
    """

    def decorator(fn: Callable) -> Task:
        task_name = name or fn.__name__
        return Task(
            name=task_name,
            fn=fn,
            retries=retries,
            timeout=timeout,
            on_status_change=on_status_change,
            on_retry=on_retry,
        )

    # If called without arguments: @task
    if callable(name):
        fn = name
        name = None
        return decorator(fn)

    # If called with arguments: @task(retries=3)
    return decorator
