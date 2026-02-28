"""
A complex workflow example using FlowWeaver's @task decorator.
Demonstrates fetching, processing, and saving data in a real-world pipeline.
"""

from sys import path as _path; from pathlib import Path as _Path
_path.insert(0, str(_Path(__file__).parent.parent / "src"))
from flowweaver.core import Workflow, task
import logging
import random
import time

logging.basicConfig(level=logging.INFO)

@task
def fetch_data(**kwargs):
    logging.info("Fetching data...")
    # Simulate data fetch
    time.sleep(1)
    data = [random.randint(1, 100) for _ in range(10)]
    logging.info(f"Fetched data: {data}")
    return data

@task
def process_data(fetch_data, **kwargs):
    logging.info("Processing data...")
    # Simulate processing
    processed = [x * 2 for x in fetch_data]
    logging.info(f"Processed data: {processed}")
    return processed

@task
def save_data(process_data, **kwargs):
    logging.info("Saving data...")
    # Simulate saving
    time.sleep(0.5)
    logging.info(f"Data saved: {process_data}")
    return "success"

if __name__ == "__main__":
    import asyncio
    wf = Workflow()
    wf.add_task(fetch_data)
    wf.add_task(process_data, depends_on=["fetch_data"])
    wf.add_task(save_data, depends_on=["process_data"])
    asyncio.run(wf.execute_async())
    print("Workflow results:")
    for name in ["fetch_data", "process_data", "save_data"]:
        print(f"{name} result:", wf.get_task_result(name))
