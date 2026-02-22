#!/usr/bin/env python3
"""
Stress Tests & Performance Benchmarks for FlowWeaver

Tests the library under heavy loads:
- Large workflows (100+ tasks)
- Deep dependency chains
- Wide parallel tasks
- Memory usage
- Execution time comparisons
"""

import sys
import time
import psutil
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from flowweaver import (
    Task,
    Workflow,
    SequentialExecutor,
    ThreadedExecutor,
    AsyncExecutor,
)


def get_memory_usage() -> float:
    """Get current process memory usage in MB."""
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / (1024 * 1024)


def benchmark_large_linear_workflow(num_tasks: int = 500):
    """Test performance with a long chain of sequential tasks."""
    print(f"\n{'=' * 70}")
    print(f"📊 BENCHMARK 1: Large Linear Workflow ({num_tasks} tasks)")
    print(f"{'=' * 70}\n")

    workflow = Workflow(name="linear_workflow")
    mem_start = get_memory_usage()

    # Create a linear chain: task_0 -> task_1 -> ... -> task_N
    for i in range(num_tasks):
        depends = [f"task_{i - 1}"] if i > 0 else None
        task = Task(name=f"task_{i}", fn=lambda x=i: x)
        workflow.add_task(task, depends_on=depends)

    mem_after_creation = get_memory_usage()
    print(
        f"Memory after creating {num_tasks} tasks: {mem_after_creation:.2f} MB (+{mem_after_creation - mem_start:.2f} MB)"
    )

    # Execute with SequentialExecutor
    executor = SequentialExecutor()
    start = time.time()
    executor.execute(workflow)
    elapsed = time.time() - start

    mem_after_execution = get_memory_usage()

    stats = workflow.get_workflow_stats()
    print(f"\nExecution Results:")
    print(f"  Executor: SequentialExecutor")
    print(f"  Total Tasks: {stats['total_tasks']}")
    print(f"  Completed: {stats['completed']}")
    print(f"  Time: {elapsed:.3f}s")
    print(f"  Tasks/sec: {stats['total_tasks'] / elapsed:.0f}")
    print(
        f"  Memory Peak: {mem_after_execution:.2f} MB (+{mem_after_execution - mem_after_creation:.2f} MB)"
    )


def benchmark_wide_parallel_workflow(num_tasks: int = 1000):
    """Test performance with many parallel independent tasks."""
    print(f"\n{'=' * 70}")
    print(f"⚡ BENCHMARK 2: Wide Parallel Workflow ({num_tasks} tasks)")
    print(f"{'=' * 70}\n")

    workflow = Workflow(name="parallel_workflow")
    mem_start = get_memory_usage()

    # Create independent tasks (all in layer 1)
    for i in range(num_tasks):
        task = Task(name=f"parallel_{i}", fn=lambda x=i: x * 2)
        workflow.add_task(task)

    mem_after_creation = get_memory_usage()
    print(
        f"Memory after creating {num_tasks} parallel tasks: {mem_after_creation:.2f} MB (+{mem_after_creation - mem_start:.2f} MB)"
    )

    # Execute with ThreadedExecutor
    executor = ThreadedExecutor(max_workers=8)
    start = time.time()
    executor.execute(workflow)
    elapsed_threaded = time.time() - start

    mem_after_threaded = get_memory_usage()

    # Compare with Sequential
    executor_seq = SequentialExecutor()
    start = time.time()
    workflow2 = Workflow(name="parallel_workflow_seq")
    for i in range(num_tasks):
        task = Task(name=f"parallel_{i}", fn=lambda x=i: x * 2)
        workflow2.add_task(task)
    executor_seq.execute(workflow2)
    elapsed_seq = time.time() - start

    print(f"\nExecution Results:")
    print(f"  Sequential Time: {elapsed_seq:.3f}s")
    print(f"  Threaded Time (8 workers): {elapsed_threaded:.3f}s")
    print(f"  Speedup: {elapsed_seq / elapsed_threaded:.2f}x")
    print(f"  Memory Peak: {mem_after_threaded:.2f} MB")


def benchmark_complex_dag(num_layers: int = 10):
    """Test performance with a complex dependency graph."""
    print(f"\n{'=' * 70}")
    print(f"🔗 BENCHMARK 3: Complex DAG ({num_layers} layers)")
    print(f"{'=' * 70}\n")

    workflow = Workflow(name="complex_dag")
    mem_start = get_memory_usage()

    tasks_per_layer = 20
    prev_layer_names = []

    # Create a pyramid DAG structure
    for layer in range(num_layers):
        current_layer = []
        deps_per_task = min(layer, 3) if layer > 0 else 0

        for task_idx in range(tasks_per_layer):
            task_name = f"layer{layer}_task{task_idx}"
            depends = (
                prev_layer_names[
                    task_idx * deps_per_task : (task_idx + 1) * deps_per_task
                ]
                if layer > 0
                else None
            )

            task = Task(name=task_name, fn=lambda x=layer: x)
            workflow.add_task(task, depends_on=depends)
            current_layer.append(task_name)

        prev_layer_names = current_layer
        print(f"  Created layer {layer + 1}/{num_layers} ({len(current_layer)} tasks)")

    mem_after_creation = get_memory_usage()

    # Get execution plan
    plan = workflow.get_execution_plan()
    print(f"\nExecution Plan Info:")
    print(f"  Total Layers: {len(plan)}")
    print(f"  Max Tasks/Layer: {max(len(layer) for layer in plan) if plan else 0}")
    print(f"  Total Tasks: {sum(len(layer) for layer in plan)}")

    # Execute
    executor = ThreadedExecutor(max_workers=4)
    start = time.time()
    executor.execute(workflow)
    elapsed = time.time() - start

    mem_after_execution = get_memory_usage()

    stats = workflow.get_workflow_stats()
    print(f"\nExecution Results:")
    print(f"  Time: {elapsed:.3f}s")
    print(f"  Tasks/sec: {stats['total_tasks'] / elapsed:.0f}")
    print(
        f"  Memory Peak: {mem_after_execution:.2f} MB (+{mem_after_execution - mem_after_creation:.2f} MB)"
    )


def benchmark_executor_comparison():
    """Compare performance of different executors on the same workflow."""
    print(f"\n{'=' * 70}")
    print(f"⚙️  BENCHMARK 4: Executor Comparison")
    print(f"{'=' * 70}\n")

    num_tasks = 100

    # Create a workflow with moderate parallelism
    def create_workflow() -> Workflow:
        wf = Workflow(name="comparison")
        for i in range(num_tasks):
            depends = [f"task_{i - 1}"] if i > 0 else None
            task = Task(name=f"task_{i}", fn=lambda x=i: x)
            wf.add_task(task, depends_on=depends)
        return wf

    results = {}

    # Sequential
    wf_seq = create_workflow()
    start = time.time()
    SequentialExecutor().execute(wf_seq)
    results["Sequential"] = time.time() - start

    # Threaded
    wf_thread = create_workflow()
    start = time.time()
    ThreadedExecutor(max_workers=4).execute(wf_thread)
    results["Threaded (4)"] = time.time() - start

    # Threaded with more workers
    wf_thread8 = create_workflow()
    start = time.time()
    ThreadedExecutor(max_workers=8).execute(wf_thread8)
    results["Threaded (8)"] = time.time() - start

    print("Executor Performance Comparison (100-task linear workflow):")
    for executor_name, exec_time in results.items():
        print(f"  {executor_name}: {exec_time:.4f}s")


def benchmark_cycle_detection():
    """Benchmark the cycle detection algorithm."""
    print(f"\n{'=' * 70}")
    print(f"🔄 BENCHMARK 5: Cycle Detection Performance")
    print(f"{'=' * 70}\n")

    # Create a large DAG
    num_tasks = 500
    workflow = Workflow(name="cycle_test_large")

    # Linear DAG (no cycles)
    print(f"Building {num_tasks}-task DAG...")
    for i in range(num_tasks):
        depends = [f"task_{i - 1}"] if i > 0 else None
        task = Task(name=f"task_{i}", fn=lambda x=i: x)
        workflow.add_task(task, depends_on=depends)

    # Test cycle detection time
    start = time.time()
    has_cycle = workflow._has_cycle()
    detection_time = time.time() - start

    print(f"\nCycle Detection Results:")
    print(f"  Tasks: {num_tasks}")
    print(f"  Has Cycle: {has_cycle}")
    print(f"  Detection Time: {detection_time * 1000:.2f}ms")
    print(f"  Expected: O(V+E) = O({num_tasks})")


def benchmark_memory_efficiency():
    """Test memory efficiency with large result sets."""
    print(f"\n{'=' * 70}")
    print(f"💾 BENCHMARK 6: Memory Efficiency")
    print(f"{'=' * 70}\n")

    def create_large_result() -> dict:
        """Create a large result (1 MB)."""
        return {"data": list(range(250000))}  # ~1 MB per task

    num_tasks = 10
    workflow = Workflow(name="memory_test")

    # Create tasks that produce large results
    for i in range(num_tasks):
        depends = [f"task_{i - 1}"] if i > 0 else None
        task = Task(name=f"task_{i}", fn=create_large_result)
        workflow.add_task(task, depends_on=depends)

    mem_before = get_memory_usage()
    print(f"Memory before execution: {mem_before:.2f} MB")

    executor = SequentialExecutor()
    executor.execute(workflow)

    mem_after = get_memory_usage()
    print(f"Memory after execution: {mem_after:.2f} MB")
    print(f"Memory increase: {mem_after - mem_before:.2f} MB")
    print(f"Expected: ~10 MB (10 tasks * 1 MB each)")


def run_all_benchmarks():
    """Run all benchmarks."""
    print("\n" + "=" * 70)
    print("🚀 FLOWWEAVER STRESS TEST & BENCHMARK SUITE")
    print("=" * 70)

    try:
        benchmark_large_linear_workflow(500)
        benchmark_wide_parallel_workflow(500)
        benchmark_complex_dag(8)
        benchmark_executor_comparison()
        benchmark_cycle_detection()
        benchmark_memory_efficiency()

        print(f"\n{'=' * 70}")
        print("✅ ALL BENCHMARKS COMPLETED SUCCESSFULLY")
        print("=" * 70 + "\n")

    except Exception as e:
        print(f"\n❌ Benchmark failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    run_all_benchmarks()
