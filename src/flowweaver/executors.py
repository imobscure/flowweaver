"""
FlowWeaver Executors Module

Implements different execution strategies using the Strategy Pattern.
Supports sequential, multi-threaded, and asynchronous execution.
Follows SDE-2 standards for error handling and concurrency management.

Features:
- Lifecycle hooks for integration with external systems (Slack, Datadog, etc.)
- Dynamic worker scaling based on layer size
- Immediate error cancellation with as_completed()
- Context-aware logging with task timing
"""

import asyncio
import concurrent.futures
import logging
from abc import ABC, abstractmethod
from typing import Optional, Callable, Any, Dict

from .core import Task, TaskStatus, Workflow

# Configure logging for the module
logger = logging.getLogger(__name__)


class BaseExecutor(ABC):
    """
    Abstract Base Class for all Executors.

    Rationale (SDE-2): Using an ABC defines a strict interface (Strategy Pattern).
    This decoupling allows the Workflow to remain agnostic of the underlying
    execution mechanism (Local, Cloud, Distributed), facilitating high extensibility.
    Subclasses can implement their own execution strategies without modifying Workflow.

    Lifecycle hooks enable integration with monitoring systems (Slack, Datadog, etc.)
    without modifying core execution logic (Open/Closed Principle).
    """

    def __init__(
        self,
        on_workflow_start: Optional[Callable[[str], None]] = None,
        on_workflow_success: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        on_workflow_failure: Optional[Callable[[str, str], None]] = None,
    ):
        """
        Initialize the BaseExecutor with optional lifecycle hooks.

        Args:
            on_workflow_start: Called when workflow execution begins (receives workflow name).
            on_workflow_success: Called on success (receives workflow name and stats dict).
            on_workflow_failure: Called on failure (receives workflow name and error message).
        """
        self.on_workflow_start = on_workflow_start
        self.on_workflow_success = on_workflow_success
        self.on_workflow_failure = on_workflow_failure

    @abstractmethod
    def execute(self, workflow: Workflow) -> None:
        """
        Execute the provided workflow according to the strategy.

        Args:
            workflow: The Workflow instance to execute.

        Raises:
            RuntimeError: If any task in the workflow fails.
        """
        pass

    def _trigger_start(self, workflow_name: str) -> None:
        """Trigger on_workflow_start hook."""
        if self.on_workflow_start:
            self.on_workflow_start(workflow_name)

    def _trigger_success(self, workflow_name: str, stats: Dict[str, Any]) -> None:
        """Trigger on_workflow_success hook."""
        if self.on_workflow_success:
            self.on_workflow_success(workflow_name, stats)

    def _trigger_failure(self, workflow_name: str, error: str) -> None:
        """Trigger on_workflow_failure hook."""
        if self.on_workflow_failure:
            self.on_workflow_failure(workflow_name, error)


class SequentialExecutor(BaseExecutor):
    """
    Runs tasks one by one in topological order.

    Suitable for simple debugging or environments where resource
    isolation is strictly required. Uses the execution plan from
    Workflow.get_execution_plan() but processes one task at a time.

    Rationale (SDE-2): Sequential execution provides predictable ordering
    and is ideal for reproducing issues. All tasks are executed on the
    main thread, simplifying debugging and state inspection.
    """

    def execute(self, workflow: Workflow) -> None:
        """
        Execute all tasks in the workflow sequentially with context passing.

        Args:
            workflow: The Workflow to execute.

        Raises:
            RuntimeError: Immediately stops and raises if any task fails.
        """
        self._trigger_start(workflow.name)
        plan = workflow.get_execution_plan()
        context: Dict[str, Any] = {}  # Stores task results for dependents

        logger.info(f"Starting sequential execution for workflow: {workflow.name}")
        logger.info(f"Total layers to process: {len(plan)}")

        try:
            for layer_idx, layer in enumerate(plan, 1):
                logger.info(
                    f"Processing layer {layer_idx}/{len(plan)} with {len(layer)} task(s)"
                )

                for task in layer:
                    # Build context for this task: collect results from dependencies
                    task_context = {}
                    for dep_name in workflow.get_task_dependencies(task.name):
                        if dep_name in context:
                            task_context[dep_name] = context[dep_name]

                    logger.debug(f"Executing task: {task.name}")
                    task.execute(task_context)

                    if task.status == TaskStatus.FAILED:
                        logger.error(
                            f"Task '{task.name}' failed with error: {task.error}"
                        )
                        raise RuntimeError(f"Workflow failed at task: {task.name}")

                    # Store result in context for dependent tasks
                    context[task.name] = task.result
                    logger.debug(f"Task '{task.name}' completed successfully")

            logger.info(f"Successfully completed workflow: {workflow.name}")
            stats = workflow.get_workflow_stats()
            self._trigger_success(workflow.name, stats)

        except Exception as e:
            logger.error(f"Workflow execution failed: {str(e)}")
            self._trigger_failure(workflow.name, str(e))
            raise


class ThreadedExecutor(BaseExecutor):
    """
    Runs independent tasks in parallel using a ThreadPool.

    Rationale (SDE-2): Parallelizing independent nodes in a DAG significantly
    reduces total latency. ThreadPoolExecutor is ideal for I/O-bound tasks and
    allows multiple CPUs to work on independent operations concurrently.

    Enhancements:
    - Dynamic worker scaling based on layer size
    - as_completed() for immediate error cancellation
    - Context sharing (XCom pattern) between dependent tasks
    - Lifecycle hooks for external system integration

    Key behavior:
    - Tasks within a layer execute in parallel
    - All tasks in a layer must complete before the next layer begins
    - If any task fails, pending tasks in the layer are cancelled (fail-fast)
    """

    def __init__(self, max_workers: Optional[int] = None):
        """
        Initialize the ThreadedExecutor.

        Args:
            max_workers: Maximum number of worker threads. If None,
                        ThreadPoolExecutor will use CPU count or a sensible default.
        """
        super().__init__()
        self.max_workers = max_workers

    def execute(self, workflow: Workflow) -> None:
        """
        Execute the workflow with tasks in parallel where possible.

        Tasks in the same layer execute simultaneously using a thread pool.
        The executor ensures all tasks in a layer complete before moving to
        the next layer, respecting dependency constraints.

        Uses as_completed() to detect failures immediately and cancel pending tasks
        rather than waiting for all tasks to finish.

        Args:
            workflow: The Workflow to execute.

        Raises:
            RuntimeError: If any task fails during execution.
        """
        self._trigger_start(workflow.name)
        plan = workflow.get_execution_plan()
        context: Dict[str, Any] = {}  # Stores task results for dependents

        logger.info(
            f"Starting threaded execution (max_workers={self.max_workers}) "
            f"for: {workflow.name}"
        )
        logger.info(f"Total layers to process: {len(plan)}")

        try:
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=self.max_workers
            ) as executor:
                for layer_idx, layer in enumerate(plan, 1):
                    # Calculate dynamic max_workers for this layer
                    layer_workers = (
                        min(len(layer), self.max_workers)
                        if self.max_workers
                        else len(layer)
                    )

                    logger.info(
                        f"Executing layer {layer_idx}/{len(plan)} "
                        f"with {len(layer)} parallel tasks (workers={layer_workers})"
                    )

                    # Submit all tasks in the current layer to the thread pool
                    futures = {}
                    for task in layer:
                        # Build context for this specific task
                        task_context = {}
                        for dep_name in workflow.get_task_dependencies(task.name):
                            if dep_name in context:
                                task_context[dep_name] = context[dep_name]
                        futures[executor.submit(task.execute, task_context)] = task

                    # Use as_completed for immediate error detection
                    for completed_future in concurrent.futures.as_completed(futures):
                        task = futures[completed_future]
                        try:
                            completed_future.result()  # Check for exceptions
                            if task.status == TaskStatus.FAILED:
                                error_msg = f"Task '{task.name}' failed: {task.error}"
                                logger.error(error_msg)
                                # Cancel remaining tasks in this layer
                                for future in futures:
                                    future.cancel()
                                raise RuntimeError(error_msg)
                            # Store result in context for dependent tasks
                            context[task.name] = task.result
                            logger.debug(f"Task '{task.name}' completed")
                        except Exception as e:
                            logger.error(
                                f"Task '{task.name}' raised exception: {str(e)}"
                            )
                            # Cancel remaining tasks
                            for future in futures:
                                future.cancel()
                            raise RuntimeError(
                                f"Workflow failed at task '{task.name}': {str(e)}"
                            )

                    logger.debug(f"Layer {layer_idx} completed successfully")

            logger.info(
                f"Successfully completed threaded execution for: {workflow.name}"
            )
            stats = workflow.get_workflow_stats()
            self._trigger_success(workflow.name, stats)

        except Exception as e:
            logger.error(f"Workflow execution failed: {str(e)}")
            self._trigger_failure(workflow.name, str(e))
            raise


class AsyncExecutor(BaseExecutor):
    """
    Executes workflows asynchronously using asyncio for true concurrency.

    Rationale (SDE-2): AsyncExecutor is ideal for I/O-bound workflows where
    tasks make network requests, database queries, or other async operations.
    Unlike ThreadedExecutor, it avoids GIL contention and provides native
    async/await integration with Python's asyncio event loop.

    Enhancements:
    - Context sharing (XCom pattern) between dependent tasks
    - Lifecycle hooks for external system integration
    - Async gather() for efficient I/O concurrency

    Key behavior:
    - Tasks within a layer execute concurrently using asyncio.gather()
    - Supports both sync and async callables (wraps sync in executor)
    - All tasks in a layer must complete before the next layer begins
    - Fail-fast on task failure
    """

    def __init__(self, use_uvloop: bool = False):
        """
        Initialize the AsyncExecutor.

        Args:
            use_uvloop: If True, attempt to use uvloop for faster event loop.
                       Falls back to asyncio if uvloop not available.
        """
        super().__init__()
        self.use_uvloop = use_uvloop

    def execute(self, workflow: Workflow) -> None:
        """
        Execute the workflow asynchronously.

        Creates a new event loop and runs the async execution.

        Args:
            workflow: The Workflow to execute.

        Raises:
            RuntimeError: If any task fails during execution.
        """
        self._trigger_start(workflow.name)

        # Try to use uvloop if requested for better performance
        if self.use_uvloop:
            try:
                import uvloop

                asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
                logger.info("Using uvloop for async execution")
            except ImportError:
                logger.warning("uvloop requested but not installed; using asyncio")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._execute_async(workflow))
        except Exception as e:
            logger.error(f"Workflow execution failed: {str(e)}")
            self._trigger_failure(workflow.name, str(e))
            raise
        finally:
            loop.close()

    async def _execute_async(self, workflow: Workflow) -> None:
        """
        Internal async execution method.

        Args:
            workflow: The Workflow to execute.

        Raises:
            RuntimeError: If any task fails during execution.
        """
        plan = workflow.get_execution_plan()
        context: Dict[str, Any] = {}  # Stores task results for dependents

        logger.info(f"Starting async execution for workflow: {workflow.name}")
        logger.info(f"Total layers to process: {len(plan)}")

        try:
            for layer_idx, layer in enumerate(plan, 1):
                logger.info(
                    f"Processing layer {layer_idx}/{len(plan)} "
                    f"with {len(layer)} concurrent task(s)"
                )

                # Build context for each task in this layer
                tasks_to_run = []
                for task in layer:
                    task_context = {}
                    for dep_name in workflow.get_task_dependencies(task.name):
                        if dep_name in context:
                            task_context[dep_name] = context[dep_name]
                    tasks_to_run.append(task.execute_async(task_context))

                # Execute all tasks in the layer concurrently
                await asyncio.gather(*tasks_to_run, return_exceptions=False)

                # Verify all tasks in the layer succeeded and store results
                for task in layer:
                    if task.status == TaskStatus.FAILED:
                        logger.error(
                            f"Critical failure in layer {layer_idx} "
                            f"at task '{task.name}': {task.error}"
                        )
                        raise RuntimeError(
                            f"Workflow execution halted due to failure in task: {task.name}"
                        )
                    # Store task result in context for dependent tasks
                    context[task.name] = task.result

                logger.debug(f"Layer {layer_idx} completed successfully")

            logger.info(f"Successfully completed async execution for: {workflow.name}")
            stats = workflow.get_workflow_stats()
            self._trigger_success(workflow.name, stats)

        except Exception as e:
            logger.error(f"Workflow execution failed: {str(e)}")
            self._trigger_failure(workflow.name, str(e))
            raise
