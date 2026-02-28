"""
Complex Workflow Example for FlowWeaver

This script demonstrates a realistic ETL (Extract, Transform, Load) pipeline:
1. Fetching user data (Simulated API call)
2. Processing data (Filtering/Formatting)
3. Aggregating results
4. Persisting state to JSON for RESUMABILITY

Usage:
    python examples/complex_sworkflow.py
"""

import time
import logging
import os
from sys import path as _path; from pathlib import Path as _Path
_path.insert(0, str(_Path(__file__).parent.parent / "src"))
from flowweaver.core import Workflow, task
from flowweaver.executors import ThreadedExecutor
from flowweaver.storage import JSONStateStore

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

@task(retries=2)
def fetch_users():
    """Simulates fetching users from an external API."""
    logging.info("Fetching user data...")
    time.sleep(1)  # Simulate I/O latency
    return [
        {"id": 1, "name": "Alice", "role": "admin"},
        {"id": 2, "name": "Bob", "role": "user"},
        {"id": 3, "name": "Charlie", "role": "user"},
    ]

@task()
def filter_admins(fetch_users):
    """Filters the list to only include admins. Injects 'fetch_users' result."""
    logging.info(f"Filtering admins from {len(fetch_users)} users...")
    return [u for u in fetch_users if u["role"] == "admin"]

@task()
def format_report(filter_admins):
    """Formats a string report based on the filtered data."""
    logging.info("Generating report...")
    names = ", ".join([u["name"] for u in filter_admins])
    return f"Admin Report: {names}"

@task()
def save_report(format_report):
    """Simulates saving the report to a persistent store."""
    logging.info(f"Final Step: Saving report -> {format_report}")
    return True

def run_complex_workflow():
    # 1. Initialize the Workflow
    wf = Workflow("UserReportingPipeline")

    # 2. Register Tasks
    # Dependencies are explicit, but data is passed automatically by FlowWeaver
    wf.add_task(fetch_users)
    wf.add_task(filter_admins, depends_on=["fetch_users"])
    wf.add_task(format_report, depends_on=["filter_admins"])
    wf.add_task(save_report, depends_on=["format_report"])

    # 3. Setup Persistence
    # This file allows us to resume if the script fails mid-way
    state_file = "workflow_state.json"
    storage = JSONStateStore(state_file)
    
    # 4. Execute using the Threaded Strategy
    executor = ThreadedExecutor(max_workers=3, storage=storage)

    logging.info("--- Starting FlowWeaver Engine ---")
    try:
        executor.execute(wf)
        logging.info("--- Execution Finished ---")
        
        print("\n" + "="*30)
        print(f"WORKFLOW: {wf.name}")
        print(f"RESULT: {wf.results.get('format_report')}")
        print("="*30)
        
    except Exception as e:
        logging.error(f"Critical Workflow Failure: {e}")

if __name__ == "__main__":
    run_complex_workflow()
