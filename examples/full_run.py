#!/usr/bin/env python3
"""
FlowWeaver Resume Demo - Full Production-Ready Example

This demonstrates:
1. @task decorator for clean task definition
2. Workflow with dependencies
3. JSONStateStore for persistence
4. ThreadedExecutor for parallel execution
5. Resumability - workflows can be stopped and restarted

Perfect for interviews and showcasing production-grade software engineering.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from flowweaver.core import Workflow, task
from flowweaver.executors import ThreadedExecutor
from flowweaver.storage import JSONStateStore
from flowweaver.utils import export_mermaid, save_mermaid, view_mermaid


# ============================================================================
# Define Tasks Using the @task Decorator
# ============================================================================


@task()
def fetch_data(**kwargs):
    """Simulate fetching data from an API."""
    print("  📥 Fetching data from source...")
    return {
        "records": [
            {"id": 1, "name": "Alice", "value": 100},
            {"id": 2, "name": "Bob", "value": 200},
            {"id": 3, "name": "Charlie", "value": 300},
        ],
        "source": "API",
        "timestamp": "2026-02-28T10:00:00",
    }


@task()
def validate_data(**kwargs):
    """Validate and enrich data."""
    fetch_data = kwargs.get("fetch_data")
    print(f"  ✓ Validating {len(fetch_data['records'])} records...")
    for record in fetch_data["records"]:
        record["valid"] = record["value"] > 0
    return {
        "status": "validated",
        "record_count": len(fetch_data["records"]),
        "records": fetch_data["records"],
    }


@task()
def transform_data(**kwargs):
    """Transform validated data."""
    validate_data = kwargs.get("validate_data")
    print(f"  🔄 Transforming {validate_data['record_count']} records...")
    transformed = [
        {
            "id": r["id"],
            "name": r["name"].upper(),
            "value_doubled": r["value"] * 2,
            "valid": r["valid"],
        }
        for r in validate_data["records"]
    ]
    return {
        "status": "transformed",
        "record_count": len(transformed),
        "records": transformed,
    }


@task()
def aggregate_results(**kwargs):
    """Aggregate and summarize results."""
    transform_data = kwargs.get("transform_data")
    print(f"  📊 Aggregating results...")
    total = sum(r["value_doubled"] for r in transform_data["records"])
    return {
        "status": "aggregated",
        "total_value": total,
        "record_count": transform_data["record_count"],
        "summary": f"Processed {transform_data['record_count']} records with total value {total}",
    }


# ============================================================================
# Main Demonstration
# ============================================================================


def main():
    """Run the workflow with storage and executor."""

    print("\n" + "=" * 75)
    print("FlowWeaver Resume Demo - Resumable, Production-Grade Workflows")
    print("=" * 75)

    # Step 1: Define the Workflow
    print("\n[1/4] Creating workflow...")
    workflow = Workflow("ResumeDemo")

    # Add tasks with @task decorator
    workflow.add_task(fetch_data)
    workflow.add_task(validate_data, depends_on=["fetch_data"])
    workflow.add_task(transform_data, depends_on=["validate_data"])
    workflow.add_task(aggregate_results, depends_on=["transform_data"])

    print(f"  ✓ Workflow created with {len(workflow.get_all_tasks())} tasks")

    # Step 2: Setup Persistence (JSONStateStore)
    print("\n[2/4] Setting up persistence...")
    state_path = Path("workflow_state.json")
    if state_path.exists():
        print("  ⚠️ Removing old workflow_state.json for clean run...")
        state_path.unlink()
    store = JSONStateStore("workflow_state.json")
    print(f"  ✓ JSONStateStore initialized (workflow_state.json)")

    # Step 3: Setup Executor (ThreadedExecutor)
    print("\n[3/4] Configuring executor...")
    executor = ThreadedExecutor(max_workers=2, storage=store)
    print(f"  ✓ ThreadedExecutor ready (max_workers=2)")

    # Step 4: Execute the Workflow
    print("\n[4/4] Executing workflow...")
    print("-" * 75)

    try:
        executor.execute(workflow)
        print("-" * 75)

        # Display Results
        print("\n✅ WORKFLOW COMPLETED SUCCESSFULLY!\n")

        all_tasks = workflow.get_all_tasks()
        for task_name in [
            "fetch_data",
            "validate_data",
            "transform_data",
            "aggregate_results",
        ]:
            task = all_tasks[task_name]
            print(f"  Task: {task_name}")
            print(f"    Status: {task.status.name}")
            print(f"    Result: {task.result}")
            print()

        print("=" * 75)
        print("Key Features Demonstrated:")
        print("=" * 75)
        print("  ✓ @task decorator for clean, testable task definition")
        print("  ✓ Workflow with dependency management (DAG)")
        print("  ✓ JSONStateStore for persistent state (resumability)")
        print("  ✓ ThreadedExecutor for parallel task execution")
        print("  ✓ XCom pattern - context passed between dependent tasks")
        print("  ✓ Thread-safe result store with RLock")
        print("=" * 75)

        print("\n💡 Resumability Demo:")
        print("   This workflow can be STOPPED and RESTARTED without re-executing")
        print("   completed tasks. Try running this script again to see resumability!")
        print()

        # --- Mermaid Visualization ---
        print("📊 Mermaid Diagram (post-execution):")
        print(export_mermaid(workflow))
        save_mermaid(workflow, "full_run_diagram.md")
        view_mermaid(workflow)

        return True

    except Exception as e:
        print(f"\n❌ Workflow failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
