#!/usr/bin/env python3
"""
Visualization Demo for FlowWeaver v0.2.0

Demonstrates the full Mermaid.js visualization toolkit:
  1. export_mermaid  – generate raw Mermaid markup
  2. save_mermaid    – write the markup to a .md file
  3. view_mermaid    – open an interactive coloured DAG in the browser

The example builds a small ETL-style workflow, executes it to populate
task statuses, and then renders the DAG with colour-coded nodes:
  - Green  = COMPLETED
  - Orange = RUNNING
  - Red    = FAILED
  - Grey   = PENDING

Usage:
    python examples/visualize_dag.py
"""

import sys
import time
from pathlib import Path

# Add src to path for local development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from flowweaver import Task, TaskStatus, Workflow, SequentialExecutor
from flowweaver.utils import export_mermaid, save_mermaid, view_mermaid


# ==================== Task Functions ====================


def fetch_raw_data() -> dict:
    """Simulate fetching raw data from an API."""
    time.sleep(0.1)
    return {"records": [1, 2, 3, 4, 5], "source": "api_v2"}


def validate_records(raw: dict) -> dict:
    """Check data quality."""
    return {"valid": len(raw.get("records", [])), "invalid": 0}


def transform_records(raw: dict) -> list[str]:
    """Normalise records into strings."""
    return [f"record_{r}" for r in raw.get("records", [])]


def load_to_warehouse(transformed: list[str]) -> dict:
    """Persist transformed data."""
    return {"loaded": len(transformed), "destination": "warehouse"}


def generate_report(validation: dict, warehouse: dict) -> str:
    """Create a human-readable summary."""
    return (
        f"Report: {validation['valid']} valid records → "
        f"{warehouse['loaded']} loaded to {warehouse['destination']}"
    )


# ==================== Workflow Setup ====================


def build_workflow() -> Workflow:
    """Construct the demo workflow DAG."""
    wf = Workflow(name="Visualization Demo")

    wf.add_task(Task(name="fetch_raw_data", fn=fetch_raw_data))
    wf.add_task(
        Task(name="validate_records", fn=lambda: validate_records(wf.get_task_result("fetch_raw_data"))),
        depends_on=["fetch_raw_data"],
    )
    wf.add_task(
        Task(name="transform_records", fn=lambda: transform_records(wf.get_task_result("fetch_raw_data"))),
        depends_on=["fetch_raw_data"],
    )
    wf.add_task(
        Task(name="load_to_warehouse", fn=lambda: load_to_warehouse(wf.get_task_result("transform_records"))),
        depends_on=["transform_records"],
    )
    wf.add_task(
        Task(
            name="generate_report",
            fn=lambda: generate_report(
                wf.get_task_result("validate_records"),
                wf.get_task_result("load_to_warehouse"),
            ),
        ),
        depends_on=["validate_records", "load_to_warehouse"],
    )

    return wf


# ==================== Main ====================


def main() -> None:
    print("\n" + "=" * 70)
    print("📊 FLOWWEAVER VISUALIZATION DEMO (v0.2.0)")
    print("=" * 70)

    wf = build_workflow()

    # ---- 1. Pre-execution: all tasks PENDING (grey) ----
    print("\n[1/3] Pre-execution diagram (all PENDING):\n")
    pre_mermaid = export_mermaid(wf, orientation="LR")
    print(pre_mermaid)

    # ---- 2. Execute the workflow ----
    print("[2/3] Running workflow...\n")
    executor = SequentialExecutor()
    executor.execute(wf)

    stats = wf.get_workflow_stats()
    print(f"  ✅ {stats['completed']}/{stats['total_tasks']} tasks completed")
    print(f"  ⏱  Execution time: {stats['total_time_seconds']:.3f}s")

    report = wf.get_task_result("generate_report")
    print(f"  📋 {report}\n")

    # ---- 3. Post-execution: all tasks COMPLETED (green) ----
    print("[3/3] Post-execution diagram (all COMPLETED):\n")
    post_mermaid = export_mermaid(wf, orientation="LR")
    print(post_mermaid)

    # Save to file
    save_mermaid(wf, "visualize_dag_diagram.md", orientation="LR")

    # Open interactive coloured graph in the browser
    view_mermaid(wf, orientation="LR")

    print("\n" + "=" * 70)
    print("✅ Visualization demo complete!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
