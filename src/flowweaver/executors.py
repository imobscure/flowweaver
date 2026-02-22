"""
FlowWeaver Executors Module

Implements different execution strategies using the Strategy Pattern.
Supports sequential, multi-threaded, and asynchronous execution.
Follows SDE-2 standards for error handling and concurrency management.
"""

import asyncio
import concurrent.futures
import logging
from abc import ABC, abstractmethod
from typing import Optional

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
    """

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
        Execute all tasks in the workflow sequentially.

        Args:
            workflow: The Workflow to execute.

        Raises:
            RuntimeError: Immediately stops and raises if any task fails.
        """
        plan = workflow.get_execution_plan()
        logger.info(f"Starting sequential execution for workflow: {workflow.name}")
        logger.info(f"Total layers to process: {len(plan)}")

        for layer_idx, layer in enumerate(plan, 1):
            logger.info(
                f"Processing layer {layer_idx}/{len(plan)} with {len(layer)} task(s)"
            )

            for task in layer:
                logger.debug(f"Executing task: {task.name}")
                task.execute()

                if task.status == TaskStatus.FAILED:
                    logger.error(f"Task '{task.name}' failed with error: {task.error}")
                    raise RuntimeError(f"Workflow failed at task: {task.name}")

                logger.debug(f"Task '{task.name}' completed successfully")

        logger.info(f"Successfully completed workflow: {workflow.name}")


class ThreadedExecutor(BaseExecutor):
    """
    Runs independent tasks in parallel using a ThreadPool.

    Rationale (SDE-2): Parallelizing independent nodes in a DAG significantly
    reduces total latency. ThreadPoolExecutor is ideal for I/O-bound tasks and
    allows multiple CPUs to work on independent operations concurrently.

    Key behavior:
    - Tasks within a layer execute in parallel
    - All tasks in a layer must complete before the next layer begins
    - If any task fails, the executor raises immediately (fail-fast)
    """

    def __init__(self, max_workers: Optional[int] = None):
        """
        Initialize the ThreadedExecutor.

        Args:
            max_workers: Maximum number of worker threads. If None,
                        ThreadPoolExecutor will use CPU count or a sensible default.
        """
        self.max_workers = max_workers

    def execute(self, workflow: Workflow) -> None:
        """
        Execute the workflow with tasks in parallel where possible.

        Tasks in the same layer execute simultaneously using a thread pool.
        The executor ensures all tasks in a layer complete before moving to
        the next layer, respecting dependency constraints.

        Args:
            workflow: The Workflow to execute.

        Raises:
            RuntimeError: If any task fails during execution.
        """
        plan = workflow.get_execution_plan()
        logger.info(
            f"Starting threaded execution (max_workers={self.max_workers}) "
            f"for: {workflow.name}"
        )
        logger.info(f"Total layers to process: {len(plan)}")

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.max_workers
        ) as executor:
            for layer_idx, layer in enumerate(plan, 1):
                logger.info(
                    f"Executing layer {layer_idx}/{len(plan)} "
                    f"with {len(layer)} parallel tasks"
                )

                # Submit all tasks in the current layer to the thread pool
                # Key insight: tasks in a layer have no dependencies on each other,
                # so it's safe to run them concurrently
                futures = {executor.submit(task.execute): task for task in layer}

                # Wait for ALL tasks in this layer to complete before proceeding
                concurrent.futures.wait(futures)

                # Verification: Ensure all tasks in the layer succeeded
                for future, task in futures.items():
                    if task.status == TaskStatus.FAILED:
                        logger.error(
                            f"Critical failure in layer {layer_idx} "
                            f"at task '{task.name}': {task.error}"
                        )
                        raise RuntimeError(
                            f"Workflow execution halted due to failure "
                            f"in task: {task.name}"
                        )

                logger.debug(f"Layer {layer_idx} completed successfully")

        logger.info(f"Successfully completed threaded execution for: {workflow.name}")


class AsyncExecutor(BaseExecutor):
    """
    Executes workflows asynchronously using asyncio for true concurrency.

    Rationale (SDE-2): AsyncExecutor is ideal for I/O-bound workflows where
    tasks make network requests, database queries, or other async operations.
    Unlike ThreadedExecutor, it avoids GIL contention and provides native
    async/await integration with Python's asyncio event loop.

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
        logger.info(f"Starting async execution for workflow: {workflow.name}")
        logger.info(f"Total layers to process: {len(plan)}")

        for layer_idx, layer in enumerate(plan, 1):
            logger.info(
                f"Processing layer {layer_idx}/{len(plan)} "
                f"with {len(layer)} concurrent task(s)"
            )

            # Execute all tasks in the layer concurrently
            tasks_to_run = [task.execute_async() for task in layer]
            await asyncio.gather(*tasks_to_run, return_exceptions=False)

            # Verify all tasks in the layer succeeded
            for task in layer:
                if task.status == TaskStatus.FAILED:
                    logger.error(
                        f"Critical failure in layer {layer_idx} "
                        f"at task '{task.name}': {task.error}"
                    )
                    raise RuntimeError(
                        f"Workflow execution halted due to failure in task: {task.name}"
                    )

            logger.debug(f"Layer {layer_idx} completed successfully")

        logger.info(f"Successfully completed async execution for: {workflow.name}")
