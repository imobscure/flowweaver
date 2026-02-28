"""
FlowWeaver Executors Module

Implements different execution strategies using the Strategy Pattern.
Supports sequential, multi-threaded, and asynchronous execution.
Includes state-awareness for workflow resumption.

Key Features:
- Strategy Pattern: Multiple execution approaches (Sequential, Threaded, Async)
- State-Aware Execution: Checks storage before running tasks (resumability)
- Dependency Resolution: Topological ordering with context injection
- Explicit Exception Handling: Futures properly resolve to catch thread exceptions
- Thread-Safe: RLock protection for concurrent context and result store access
"""

import asyncio
import concurrent.futures
import logging
import threading
from threading import RLock
from abc import ABC, abstractmethod
from typing import Optional, Any, Dict

from .core import Task, TaskStatus, Workflow

logger = logging.getLogger(__name__)


class BaseExecutor(ABC):
    """
    Abstract Base Class for all Executors.

    Using the Strategy Pattern allows the Workflow to remain agnostic of the execution environment (local threads vs. distributed nodes). State store integration enables resumability - skipping already-completed tasks.
    """

    def __init__(self, storage: Optional[Any] = None):
        """
        Initialize the BaseExecutor.

        Args:
            storage: Optional StateStore backend for task resumability.
        """
        self.storage = storage
        """
        Initialize the BaseExecutor.

        Args:
            storage: Optional StateStore backend for task resumability.
        """
        self.storage = storage

    @abstractmethod
    def execute(self, workflow: Workflow) -> None:
        """
        Execute the provided workflow according to the strategy.

        Args:
            workflow: The Workflow instance to execute.

        Raises:
            RuntimeError: If any task fails.
        """
        pass

    def _should_skip(self, task: Task) -> bool:
        """Check if a task was already successfully completed in a previous run."""
        return task.status == TaskStatus.COMPLETED


class SequentialExecutor(BaseExecutor):
    """
    Runs tasks one by one in topological order.
    Useful for debugging and environments with limited resources.
    """

    def execute(self, workflow: Workflow) -> None:
        """Execute all tasks in the workflow sequentially with context passing."""
        plan = workflow.get_execution_plan()
        context: Dict[str, Any] = {}

        if self.storage:
            self.storage.load_state(workflow)

        logger.info(f"Starting sequential execution for workflow: {workflow.name}")

        try:
            for layer in plan:
                for task in layer:
                    if self._should_skip(task):
                        logger.info(f"Skipping completed task: {task.name}", extra={"workflow": workflow.name, "task": task.name})
                        context[task.name] = task.result
                        continue

                    # Build context from dependencies
                    task_context = {}
                    for dep_name in workflow.get_task_dependencies(task.name):
                        if dep_name in context:
                            task_context[dep_name] = context[dep_name]

                    logger.debug(f"Executing task: {task.name}", extra={"workflow": workflow.name, "task": task.name})

                    try:
                        task.execute(task_context)
                        if task.status == TaskStatus.COMPLETED:
                            context[task.name] = task.result
                            workflow._store_task_result(task.name, task.result)
                        else:
                            raise RuntimeError(f"Task '{task.name}' failed: {task.error}")
                    except Exception as e:
                        logger.exception(f"Task '{task.name}' failed", extra={"workflow": workflow.name, "task": task.name})
                        raise RuntimeError(f"Workflow failed at task: {task.name}") from e

                if self.storage:
                    self.storage.save_state(workflow)

            logger.info(f"Successfully completed workflow: {workflow.name}", extra={"workflow": workflow.name})

        except Exception as e:
            logger.exception(f"Workflow execution failed", extra={"workflow": workflow.name})
            raise


class ThreadedExecutor(BaseExecutor):
    """
    Parallel executor using a ThreadPool.
    Groups tasks by layer to maximize concurrency while respecting dependencies.
    """

    def __init__(self, max_workers: int = 4, storage: Optional[Any] = None):
        super().__init__(storage)
        self.max_workers = max_workers

    def execute(self, workflow: Workflow) -> None:
        """
        Execute workflow with tasks in parallel using ThreadPool.

        Tasks within each layer execute concurrently, but all must complete
        before the next layer begins. Explicitly fetches future results to
        catch and propagate any exceptions raised during thread execution.
        """
        plan = workflow.get_execution_plan()
        context: Dict[str, Any] = {}
        context_lock = threading.RLock()

        if self.storage:
            self.storage.load_state(workflow)

        logger.info(
            f"Starting threaded execution (max_workers={self.max_workers}) "
            f"for: {workflow.name}"
        )

        try:
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=self.max_workers
            ) as executor:
                for i, layer in enumerate(plan):
                    # Filter out tasks that were already completed (Resumability)
                    tasks_to_run = [t for t in layer if not self._should_skip(t)]

                    if not tasks_to_run:
                        logger.info(
                            f"Layer {i + 1}: All tasks already completed. Skipping."
                        )
                        continue

                    logger.info(
                        f"Executing layer {i + 1}/{len(plan)} with {len(tasks_to_run)} tasks"
                    )

                    # Run tasks with injected context
                    futures = {}
                    for task in tasks_to_run:
                        # Build context for this task from dependencies
                        task_context = {}
                        for dep_name in workflow.get_task_dependencies(task.name):
                            with context_lock:
                                if dep_name in context:
                                    task_context[dep_name] = context[dep_name]
                        futures[executor.submit(task.execute, task_context)] = task

                    # Wait for the entire layer to finish
                    concurrent.futures.wait(futures)

                    # Post-execution: Explicitly fetch results and check for errors
                    for future, task in futures.items():
                        try:
                            # Ensure we catch exceptions raised within threads
                            future.result()
                            if task.status == TaskStatus.COMPLETED:
                                with context_lock:
                                    context[task.name] = task.result
                                workflow._store_task_result(task.name, task.result)
                            else:
                                raise RuntimeError(
                                    f"Task '{task.name}' ended in status {task.status}"
                                )
                        except Exception as e:
                            logger.error(f"Critical failure in task '{task.name}': {e}")
                            raise RuntimeError(
                                f"Workflow execution halted due to failure in task: {task.name}"
                            ) from e

                    # Persist state after each layer completes successfully
                    if self.storage:
                        self.storage.save_state(workflow)

            logger.info(f"Successfully completed workflow: {workflow.name}")

        except Exception as e:
            logger.error(f"Workflow execution failed: {str(e)}")
            raise


class AsyncExecutor(BaseExecutor):
    """
    Executes workflows asynchronously using asyncio for true concurrency.
    Ideal for I/O-bound tasks that benefit from async operations.
    """

    def __init__(self, use_uvloop: bool = False, storage: Optional[Any] = None):
        """
        Initialize the AsyncExecutor.

        Args:
            use_uvloop: If True, attempt to use uvloop for faster event loop.
            storage: Optional StateStore for task resumability.
        """
        super().__init__(storage)
        self.use_uvloop = use_uvloop

    def execute(self, workflow: Workflow) -> None:
        """Execute the workflow asynchronously."""
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
            raise
        finally:
            loop.close()

    async def _execute_async(self, workflow: Workflow) -> None:
        """Internal async execution method."""
        plan = workflow.get_execution_plan()
        context: Dict[str, Any] = {}

        if self.storage:
            self.storage.load_state(workflow)

        logger.info(f"Starting async execution for workflow: {workflow.name}")

        try:
            for i, layer in enumerate(plan):
                # Filter out tasks that were already completed
                tasks_to_run = [t for t in layer if not self._should_skip(t)]

                if not tasks_to_run:
                    logger.info(
                        f"Layer {i + 1}: All tasks already completed. Skipping."
                    )
                    continue

                logger.info(
                    f"Executing layer {i + 1}/{len(plan)} with {len(tasks_to_run)} tasks"
                )

                # Build async coroutines for each task
                coros = []
                for task in tasks_to_run:
                    # Build context for this task from dependencies
                    task_context = {}
                    for dep_name in workflow.get_task_dependencies(task.name):
                        if dep_name in context:
                            task_context[dep_name] = context[dep_name]
                    coros.append(self._run_task_async(workflow, task, task_context))

                # Execute all tasks in the layer concurrently
                await asyncio.gather(*coros, return_exceptions=False)

                # Collect results after execution
                for task in tasks_to_run:
                    if task.status == TaskStatus.COMPLETED:
                        context[task.name] = task.result

                # Persist state after each layer completes successfully
                if self.storage:
                    self.storage.save_state(workflow)

            logger.info(f"Successfully completed workflow: {workflow.name}")

        except Exception as e:
            logger.error(f"Workflow execution failed: {str(e)}")
            raise

    async def _run_task_async(
        self, workflow: Workflow, task: Task, context: Dict[str, Any]
    ) -> None:
        """Helper to run a single task and handle exceptions. Uses thread pool for sync tasks."""
        try:
            if hasattr(task, "execute_async") and callable(task.execute_async):
                await task.execute_async(context)
            elif task.is_async():
                await task.fn(**(context or {}))
            else:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, task.execute, context)

            if task.status == TaskStatus.COMPLETED:
                workflow._store_task_result(task.name, task.result)
            else:
                raise RuntimeError(f"Task '{task.name}' ended in status {task.status}")
        except Exception as e:
            logger.exception(f"Critical failure in task '{task.name}'", extra={"workflow": workflow.name, "task": task.name})
            raise RuntimeError(
                f"Workflow execution halted due to failure in task: {task.name}"
            ) from e
