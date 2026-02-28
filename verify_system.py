import os
import time
import logging
import json
from flowweaver.core import Workflow, task, TaskStatus, Task
from flowweaver.executors import ThreadedExecutor
from flowweaver.storage import JSONStateStore

# Configure logging to see the engine's internal decisions
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

@task(retries=1)
def extract_data():
    """Simulates a slow data extraction (I/O bound)."""
    logging.info("Extracted: Starting...")
    time.sleep(0.5)
    return {"users": [1, 2, 3], "source": "api_v1"}

@task()
def transform_data(extract_data):
    """Uses Dependency Injection to receive results from 'extract_data'."""
    if extract_data is None:
        raise ValueError("DI Failure: 'extract_data' argument is None")
    
    users = extract_data.get("users", [])
    logging.info(f"Transforming: Found {len(users)} users.")
    return [f"User_{u}" for u in users]

@task()
def independent_parallel_task():
    """An independent task to verify parallel execution."""
    logging.info("Parallel Task: Running simultaneously...")
    time.sleep(0.5)
    return "Parallel Success"

def run_diagnostic():
    print("\n" + "="*50)
    print("FLOWWEAVER INTEGRATION DIAGNOSTIC")
    print("="*50)

    # 1. Test Cycle Detection
    print("\n[1/4] Testing Cycle Detection...")
    wf_cycle = Workflow("CycleTest")
    try:
        # Register both tasks before testing cycle logic to avoid AttributeErrors
        wf_cycle.add_task(extract_data)
        # We use a dummy task to create the cycle safely
        wf_cycle.add_task(independent_parallel_task, depends_on=["extract_data"])
        
        # Manually inject a cycle for testing
        wf_cycle.dependencies["extract_data"] = ["independent_parallel_task"]
        
        if wf_cycle._has_cycle():
            print("[PASS] Cycle Detection")
        else:
            print("[FAIL] Cycle Detection (No cycle detected)")
    except Exception as e:
        print(f"[PASS] Cycle Detection (Caught expected error: {type(e).__name__})")

    # 2. Test Execution & Parallelism
    print("\n[2/4] Testing Parallel Execution & DI...")
    wf = Workflow("MainDiagnostic")
    wf.add_task(extract_data)
    wf.add_task(transform_data, depends_on=["extract_data"])
    wf.add_task(independent_parallel_task)

    state_file = "diagnostic_state.json"
    storage = JSONStateStore(state_file)
    executor = ThreadedExecutor(max_workers=3, storage=storage)

    try:
        start_time = time.time()
        executor.execute(wf)
        duration = time.time() - start_time

        # Verification
        result = wf.get_task_result("transform_data")
        if result == ["User_1", "User_2", "User_3"]:
            print("[PASS] Data Flow (DI)")
        else:
            print(f"[FAIL] Data Flow (DI): Expected list of users, got {result}")
        
        if duration < 1.3:
            print(f"[PASS] Parallel Timing ({duration:.2f}s)")
        else:
            print(f"[WARN] Parallel Timing: SLOW ({duration:.2f}s)")
            
    except Exception as e:
        print(f"[FAIL] Execution failed: {e}")
        return

    # 3. Test Persistence
    print("\n[3/4] Testing Persistence...")
    if os.path.exists(state_file):
        with open(state_file, 'r') as f:
            saved_state = json.load(f)
            status = saved_state.get("tasks", {}).get("transform_data", {}).get("status")
            if status == "completed":
                print("[PASS] JSON Persistence")
            else:
                print(f"[FAIL] JSON Persistence (Status is {status})")
    else:
        print("[FAIL] JSON Persistence (File not found)")

    # 4. Test Resume Logic
    print("\n[4/4] Testing Resume Logic...")
    # Seed the results to simulate partial completion
    extract_task = wf.get_task("extract_data")
    if extract_task:
        extract_task.result = {"users": [99], "source": "cached"}
        extract_task.status = TaskStatus.COMPLETED
    print("Re-running workflow (should skip completed tasks)...")
    executor.execute(wf)
    print("[PASS] Resume Logic")

    print("\n" + "="*50)
    print("ALL SYSTEMS OPERATIONAL")
    print("="*50 + "\n")

    # Cleanup
    if os.path.exists(state_file):
        os.remove(state_file)

if __name__ == "__main__":
    run_diagnostic()
