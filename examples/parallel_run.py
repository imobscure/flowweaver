"""
Phase 2 Example: Parallel Execution with ThreadedExecutor

This example demonstrates how FlowWeaver enables parallel task execution
while respecting dependency constraints. We'll create a workflow with
multiple tasks at different dependency levels and execute them using
both SequentialExecutor and ThreadedExecutor for comparison.

Workflow Structure:
    task_a ------------->  task_c -------> task_e
           \            /              /
            task_b ----->  task_d ----
                |__________|

Tasks task_a and task_b can run in parallel (no dependencies).
Tasks task_c and task_d can run in parallel (both depend on a & b).
Task task_e depends on both c & d.

Expected Layers:
Layer 1: [task_a, task_b]
Layer 2: [task_c, task_d]
Layer 3: [task_e]
"""

import logging
import time
from flowweaver import Task, TaskStatus, Workflow, SequentialExecutor, ThreadedExecutor

# Configure logging to see execution details
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


def task_a_fn():
    """Simulates a 1-second I/O operation."""
    logger.info("task_a: Starting (1 second sleep)")
    time.sleep(1)
    logger.info("task_a: Completed")
    return "result_a"


def task_b_fn():
    """Simulates a 1-second I/O operation."""
    logger.info("task_b: Starting (1 second sleep)")
    time.sleep(1)
    logger.info("task_b: Completed")
    return "result_b"


def task_c_fn():
    """Depends on a and b."""
    logger.info("task_c: Starting (0.5 second sleep)")
    time.sleep(0.5)
    logger.info("task_c: Completed")
    return "result_c"


def task_d_fn():
    """Depends on a and b."""
    logger.info("task_d: Starting (0.5 second sleep)")
    time.sleep(0.5)
    logger.info("task_d: Completed")
    return "result_d"


def task_e_fn():
    """Depends on c and d."""
    logger.info("task_e: Starting (0.5 second sleep)")
    time.sleep(0.5)
    logger.info("task_e: Completed")
    return "result_e"


def main():
    """Demonstrate parallel execution with FlowWeaver."""

    # Create tasks
    task_a = Task(name="task_a", fn=task_a_fn)
    task_b = Task(name="task_b", fn=task_b_fn)
    task_c = Task(name="task_c", fn=task_c_fn)
    task_d = Task(name="task_d", fn=task_d_fn)
    task_e = Task(name="task_e", fn=task_e_fn)

    # Build the workflow
    workflow = Workflow(name="parallel_example")

    # Add tasks with dependencies
    workflow.add_task(task_a)  # No dependencies
    workflow.add_task(task_b)  # No dependencies
    workflow.add_task(task_c, depends_on=["task_a", "task_b"])
    workflow.add_task(task_d, depends_on=["task_a", "task_b"])
    workflow.add_task(task_e, depends_on=["task_c", "task_d"])

    # Get and display the execution plan
    plan = workflow.get_execution_plan()
    print("\n" + "=" * 80)
    print("EXECUTION PLAN")
    print("=" * 80)
    for layer_idx, layer in enumerate(plan, 1):
        task_names = [t.name for t in layer]
        print(f"Layer {layer_idx}: {task_names}")
    print("=" * 80 + "\n")

    # Test 1: Sequential Execution
    print("\n" + "=" * 80)
    print("TEST 1: SEQUENTIAL EXECUTION")
    print("=" * 80)
    print("Running tasks one by one in topological order...")
    print("Expected time: ~3.5 seconds (1 + 1 + 0.5 + 0.5 + 0.5)\n")

    # Reset task states
    for task in [task_a, task_b, task_c, task_d, task_e]:
        task.status = TaskStatus.PENDING
        task.result = None
        task.error = None

    seq_executor = SequentialExecutor()
    start_time = time.time()
    try:
        seq_executor.execute(workflow)
        seq_time = time.time() - start_time
        print(f"\n✓ Sequential execution completed in {seq_time:.2f} seconds")
    except RuntimeError as e:
        print(f"\n✗ Sequential execution failed: {e}")

    # Test 2: Threaded Execution
    print("\n" + "=" * 80)
    print("TEST 2: THREADED EXECUTION")
    print("=" * 80)
    print("Running tasks in parallel within each layer...")
    print("Expected time: ~2.5 seconds (1 + 0.5 + 0.5)\n")

    # Reset task states
    for task in [task_a, task_b, task_c, task_d, task_e]:
        task.status = TaskStatus.PENDING
        task.result = None
        task.error = None

    threaded_executor = ThreadedExecutor(max_workers=4)
    start_time = time.time()
    try:
        threaded_executor.execute(workflow)
        threaded_time = time.time() - start_time
        print(f"\n✓ Threaded execution completed in {threaded_time:.2f} seconds")
    except RuntimeError as e:
        print(f"\n✗ Threaded execution failed: {e}")

    # Performance comparison
    print("\n" + "=" * 80)
    print("PERFORMANCE COMPARISON")
    print("=" * 80)
    print(f"Sequential time:  {seq_time:.2f}s")
    print(f"Threaded time:    {threaded_time:.2f}s")
    if seq_time > 0:
        speedup = seq_time / threaded_time
        print(f"Speedup:          {speedup:.2f}x faster with threading")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
