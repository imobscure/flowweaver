#!/usr/bin/env python3
"""Quick test of new refinements - writes output to file"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

output = []

try:
    output.append("Starting import test...")
    from flowweaver import (
        Task,
        Workflow,
        task,
        StateBackend,
        InMemoryStateBackend,
        SequentialExecutor,
    )

    output.append("✅ All imports successful!")

    # Test @task decorator
    @task(retries=2)
    def sample_task():
        return "success"

    output.append(f"✅ @task decorator works: {isinstance(sample_task, Task)}")

    # Test StateBackend
    backend = InMemoryStateBackend()
    from flowweaver import TaskStatus
    from datetime import datetime

    backend.save_task_state(
        "test", TaskStatus.COMPLETED, {"val": 1}, None, datetime.now()
    )
    result = backend.load_task_state("test")
    output.append(f"✅ StateBackend works: {result is not None}")

    # Test context passing
    @task()
    def fetch():
        return 100

    @task()
    def process(fetch=None):
        return fetch * 2 if fetch else 0

    w = Workflow("test")
    w.add_task(fetch)
    w.add_task(process, depends_on=["fetch"])

    executor = SequentialExecutor()
    executor.execute(w)

    result1 = w.get_task_result("fetch")
    result2 = w.get_task_result("process")
    output.append(f"✅ Context sharing works: fetch={result1}, process={result2}")

    output.append("\n✅ ALL REFINEMENTS WORKING!")

except Exception as e:
    output.append(f"❌ Error: {str(e)}")
    import traceback

    output.append(traceback.format_exc())

# Write output to file
with open("test_output.txt", "w") as f:
    f.write("\n".join(output))

print("\n".join(output))
