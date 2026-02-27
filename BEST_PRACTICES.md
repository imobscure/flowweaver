# FlowWeaver v0.3.2 - Production Best Practices

## Table of Contents

1. [Workflow Design](#workflow-design)
2. [Task Design](#task-design)
3. [Error Handling & Resilience](#error-handling--resilience)
4. [Performance Optimization](#performance-optimization)
5. [Data Flow & Context](#data-flow--context)
6. [Concurrency & Thread Safety](#concurrency--thread-safety)
7. [Persistence & Resumability](#persistence--resumability)
8. [Testing Strategies](#testing-strategies)
9. [Monitoring & Observability](#monitoring--observability)
10. [Common Pitfalls](#common-pitfalls)

---

## Workflow Design

### 1. Keep Workflows Focused

**✓ Good**: Single responsibility - one clear purpose
```python
from flowweaver import Workflow, task

# Clear, focused workflow
workflow = Workflow(
    name="customer_data_etl",
    description="Extract, transform, load customer data from CRM to warehouse"
)

@task()
def extract_from_crm():
    return fetch_crm_data()

@task()
def validate_records(extract_from_crm=None):
    return validate_customer_data(extract_from_crm)

@task()
def load_to_warehouse(validate_records=None):
    return upload_to_db(validate_records)

workflow.add_task(extract_from_crm)
workflow.add_task(validate_records, depends_on=["extract_from_crm"])
workflow.add_task(load_to_warehouse, depends_on=["validate_records"])
```

**✗ Bad**: Mixing unrelated concerns
```python
# Do NOT do this
workflow = Workflow("everything")  # Too vague!

workflow.add_task(Task("fetch_data", fetch_data))
workflow.add_task(Task("send_email", send_email))
workflow.add_task(Task("update_cache", update_cache))
workflow.add_task(Task("log_metrics", log_metrics))
# No clear dependencies or purpose
```

### 2. Explicit Dependency Declaration

**✓ Good**: Clear `depends_on` declarations
```python
workflow.add_task(fetch_data)
workflow.add_task(
    validate_data,
    depends_on=["fetch_data"]  # Explicit!
)
workflow.add_task(
    transform_data,
    depends_on=["fetch_data", "validate_data"]  # All dependencies listed
)
```

**✗ Bad**: Implicit dependencies (hard to debug)
```python
# Never rely on task execution order without depends_on
workflow.add_task(fetch_data)
workflow.add_task(validate_data)  # Assumes fetch_data ran first
workflow.add_task(transform_data)  # What depends on what?
```

### 3. Design for Resumability

**✓ Good**: Idempotent tasks that work with state store
```python
# Each task is idempotent - safe to re-run
@task()
def fetch_daily_data():
    # If run twice, returns same data (not duplicates)
    return get_data_for_date(today())

@task()
def transform(fetch_daily_data=None):
    # Deterministic - same input = same output
    return transform_records(fetch_daily_data)

# Use state store to skip already-completed tasks
state_store = SQLiteStateStore("/var/lib/state.db")
executor = SequentialExecutor(state_store=state_store)
executor.execute(workflow)  # Resumes from where it left off
```

**✗ Bad**: Non-idempotent tasks (problems on resume)
```python
counter = 0

@task()
def increment():
    global counter
    counter += 1  # NOT IDEMPOTENT
    return counter

# If resumed:
# Run 1: counter = 1
# Run 2: counter incremented again (wrong!)
```

---

## Task Design

### 1. Single Responsibility per Task

**✓ Good**: Tasks do one thing
```python
@task()
def extract_users():
    """Get user records"""
    return db.query("SELECT * FROM users")

@task()
def extract_orders():
    """Get order records"""
    return db.query("SELECT * FROM orders")

@task()
def validate_data(extract_users=None, extract_orders=None):
    """Validate both sets"""
    assert extract_users  # Check users present
    assert extract_orders  # Check orders present
    return True
```

**✗ Bad**: Tasks doing too much
```python
@task()
def do_everything(extract_users=None, extract_orders=None, extract_products=None):
    # Huge, hard to test, hard to debug
    validate_users(extract_users)
    validate_orders(extract_orders)
    validate_products(extract_products)
    merge_data(extract_users, extract_orders)
    upload_to_warehouse()
    send_notification()
    return "done"
```

### 2. Make Tasks Stateless

**✓ Good**: All data passed as parameters
```python
@task()
def process_batch(data=None):  # Receives data as parameter
    if not data:
        raise ValueError("No data provided")
    
    return [transform_record(r) for r in data]
```

**✗ Bad**: Tasks relying on global/external state
```python
GLOBAL_CONFIG = {"batch_size": 100}  # BAD

@task()
def process_batch():
    # Depends on global state (hard to test, non-deterministic)
    return process_records(GLOBAL_CONFIG["batch_size"])
```

### 3. Proper Function Signatures for XCom

**✓ Good**: Accept upstream results via `**kwargs`
```python
@task()
def fetch_users():
    return [{"id": 1, "name": "Alice"}]

@task()
def fetch_orders():
    return [{"user_id": 1, "amount": 100}]

@task()
def join_data(fetch_users=None, fetch_orders=None):
    # XCom pattern: receives upstream results by task name
    users_by_id = {u["id"]: u for u in fetch_users}
    
    return [
        {
            "user": users_by_id[o["user_id"]],
            "order": o
        }
        for o in fetch_orders
    ]

workflow.add_task(fetch_users)
workflow.add_task(fetch_orders)
workflow.add_task(join_data, depends_on=["fetch_users", "fetch_orders"])
```

**✗ Bad**: Not accepting parameters
```python
@task()
def join_data():  # No parameters!
    # How to access fetch_users and fetch_orders?
    # This won't work in workflow context
    return "confused"
```

### 4. Meaningful Task Names

**✓ Good**: Descriptive names
```python
workflow.add_task(Task("fetch_raw_customer_data", fetch_function))
workflow.add_task(Task("validate_customer_records", validate_function))
workflow.add_task(Task("transform_for_warehouse", transform_function))
```

**✗ Bad**: Vague names
```python
workflow.add_task(Task("step1", fetch_function))
workflow.add_task(Task("step2", validate_function))
workflow.add_task(Task("step3", transform_function))
# What does each step do? Hard to debug.
```

---

## Error Handling & Resilience

### 1. Use Retries for Transient Failures

**✓ Good**: Retry on network/temporary errors
```python
@task(retries=3)  # Retry up to 3 times
def fetch_from_unstable_api():
    """Network calls often have transient failures"""
    try:
        return requests.get("https://api.example.com/data").json()
    except requests.ConnectionError:
        # Will be retried automatically
        raise

@task(retries=2)
def database_write():
    """Transient DB locks should retry"""
    try:
        db.write(data)
    except DatabaseLockError:
        raise  # Will retry

workflow.add_task(fetch_from_unstable_api)
workflow.add_task(database_write)
```

**✗ Bad**: No retries for potentially failing operations
```python
@task()  # No retries!
def fetch_from_api():
    # Network can fail - should retry
    return requests.get("https://api.example.com/data").json()

@task()  # No retries!
def database_write():
    # Temporary lock could cause failure
    db.write(data)
```

### 2. Timeouts Prevent Hung Tasks

**✓ Good**: Set reasonable timeouts
```python
@task(timeout=30)  # 30 seconds max
def fetch_api_data():
    """API often times out - protect with timeout"""
    return make_request("https://slow-api.example.com")

@task(timeout=300)  # 5 minutes for heavy computation
def process_large_dataset():
    """CPU-bound task with reasonable upper bound"""
    return expensive_calculation()

@task(timeout=3600)  # 1 hour for batch job
def nightly_batch_job():
    """Long-running but should complete within SLA"""
    return process_all_records()
```

**✗ Bad**: No timeout (task could hang forever)
```python
@task()  # No timeout!
def long_running_task():
    while True:  # Could hang!
        process_data()

# If network fails, this hangs infinitely
```

### 3. Explicit Error Handling

**✓ Good**: Handle specific errors
```python
import logging

logger = logging.getLogger(__name__)

@task(retries=2)
def fetch_data():
    try:
        return call_api()
    except requests.Timeout:
        logger.error("API timeout")
        raise  # Retry
    except requests.HTTPError as e:
        if e.response.status_code == 429:  # Rate limited
            logger.error("Rate limited, should retry")
            raise
        else:
            logger.error(f"HTTP error {e.response.status_code}")
            raise  # Will fail (no retry) - indicate programmer error
    except requests.JSONDecodeError:
        logger.error("Invalid response format")
        raise  # Will fail - data issue, not transient
```

**✗ Bad**: Catching everything
```python
@task()
def fetch_data():
    try:
        return call_api()
    except Exception:  # Too broad!
        return None  # Hides bugs, inconsistent behavior
```

---

## Performance Optimization

### 1. Choose Right Executor

**✓ Good**: Match executor to workload
```python
# I/O-bound (network, database)
io_executor = ThreadedExecutor(max_workers=8)
io_executor.execute(io_workflow)

# CPU-bound (calculations)
cpu_executor = SequentialExecutor()  # Single thread
cpu_executor.execute(cpu_workflow)

# Async workload
async_executor = AsyncExecutor(max_concurrent=50)
await async_executor.execute(async_workflow)
```

**✗ Bad**: Using same executor for all
```python
# All I/O-bound tasks using SequentialExecutor
# Wastes time waiting for I/O instead of parallelizing
executor = SequentialExecutor()
executor.execute(workflow)  # Very slow for I/O-bound
```

### 2. Optimize Thread Pool Size

**✓ Good**: Tune based on profiling
```python
import os
import time

cpu_cores = os.cpu_count()

# For I/O-bound: empirical testing showed optimal at 2x cores
optimal_workers = cpu_cores * 2

executor = ThreadedExecutor(max_workers=optimal_workers)

start = time.time()
executor.execute(workflow)
duration = time.time() - start

print(f"Completed in {duration}s with {optimal_workers} workers")
```

**✗ Bad**: Arbitrary numbers
```python
# Using max_workers=100 for everything
executor = ThreadedExecutor(max_workers=100)  # Over-subscribed!
executor.execute(workflow)  # Context switching overhead
```

### 3. Batch Small Tasks

**✓ Good**: Combine related work
```python
@task()
def fetch_user_batch():
    """Fetch 100 users in one call (efficient)"""
    return db.query("SELECT * FROM users LIMIT 100")

@task()
def process_batch(fetch_user_batch=None):
    """Process entire batch in one task"""
    return [heavy_process(u) for u in fetch_user_batch]
```

**✗ Bad**: One task per record
```python
for user_id in range(1000):
    workflow.add_task(
        Task(f"process_user_{user_id}", lambda: process_user(user_id))
    )
# 1000 tasks = huge overhead, slow execution
```

### 4. Use State Store for Large Results

**✓ Good**: Persist large results to disk
```python
from flowweaver import SQLiteStateStore

@task()
def process_large_file():
    """Returns 100MB of data"""
    return load_and_process_file("large.csv")

workflow = Workflow("large_data")
workflow.add_task(process_large_file)

# SQLite state store keeps large results on disk
state_store = SQLiteStateStore("/var/lib/state.db")
executor = SequentialExecutor(state_store=state_store)
executor.execute(workflow)
```

**✗ Bad**: Keeping huge results in memory
```python
# Without state store, result stays in memory
# workflow._result_store grows unbounded
executor = SequentialExecutor()  # No state_store
executor.execute(workflow)  # Large result stays in RAM
```

---

## Data Flow & Context

### 1. Leverage XCom Pattern

**✓ Good**: Tasks communicate via context
```python
@task()
def extract():
    return {"users": get_users(), "orders": get_orders()}

@task()
def validate(extract=None):
    # Receives extract result automatically via XCom
    assert extract["users"]
    assert extract["orders"]
    return True

@task()
def transform(extract=None, validate=None):
    # Can access multiple dependencies
    if validate:
        return process(extract)

workflow.add_task(extract)
workflow.add_task(validate, depends_on=["extract"])
workflow.add_task(transform, depends_on=["extract", "validate"])
```

**✗ Bad**: Task reaching into workflow internals
```python
@task()
def transform():
    # Reaching into workflow internals - fragile!
    extract_result = some_global_workflow._result_store["extract"]
    return process(extract_result)
```

### 2. Type Your Context

**✓ Good**: Define context types
```python
from typing import TypedDict

class UserData(TypedDict):
    id: int
    name: str
    email: str

@task()
def fetch_users() -> list[UserData]:
    return [{"id": 1, "name": "Alice", "email": "alice@example.com"}]

@task()
def process_users(fetch_users: list[UserData] | None = None) -> int:
    # Type hints make it clear what data flows
    if not fetch_users:
        return 0
    return len(fetch_users)
```

**✗ Bad**: Unclear data types
```python
@task()
def fetch_users():
    return ...  # Returns what? Lists? Dicts? Unknown

@task()
def process_users(fetch_users=None):
    # What should I expect? No type hints
    return something(fetch_users)
```

---

## Concurrency & Thread Safety

### 1. ThreadedExecutor is Thread-Safe

**✓ Good**: Use ThreadedExecutor safely
```python
# ThreadedExecutor automatically uses RLock for:
# - Result store updates
# - Context dict updates
# - Task execution

executor = ThreadedExecutor(max_workers=4)
executor.execute(workflow)  # Safe for concurrent access
```

### 2. Protect External Shared State

**✓ Good**: Thread-safe access to external resources
```python
import threading

# Shared resource
shared_cache = {}
cache_lock = threading.RLock()

@task()
def update_cache(data=None):
    """Safely update shared cache"""
    with cache_lock:  # Protect against race conditions
        shared_cache.update(data)
    return True

@task()
def read_cache():
    """Safely read shared cache"""
    with cache_lock:
        return dict(shared_cache)  # Return copy

executor = ThreadedExecutor(max_workers=4)
executor.execute(workflow)
```

**✗ Bad**: Unprotected concurrent access
```python
shared_counter = 0

@task()
def increment_counter():
    global shared_counter
    shared_counter += 1  # RACE CONDITION!
    return shared_counter

executor = ThreadedExecutor(max_workers=4)
executor.execute(workflow)
# Results are unpredictable - lost updates
```

### 3. Avoid Locks in Task Functions

**✓ Good**: Keep tasks lock-free
```python
@task()
def process_data(data=None):
    # No locks - just data processing
    return [transform(item) for item in data]
```

**✗ Bad**: Holding locks in tasks
```python
global_lock = threading.Lock()

@task()
def process_with_lock(data=None):
    with global_lock:
        # Holding lock during entire task execution
        # Serializes all tasks - defeats threading
        return slow_processing(data)

# ThreadedExecutor will run serially, defeating parallelism
```

---

## Persistence & Resumability

### 1. Design for Resumability from Day One

**✓ Good**: Idempotent tasks with state store
```python
@task()
def fetch_daily_report():
    """Safe to run multiple times same day"""
    # Deterministic - same input date = same output
    return fetch_report_for_date(today())

@task()
def validate_report(fetch_daily_report=None):
    """Validate the report"""
    return is_valid(fetch_daily_report)

# Can be resumed safely - skips completed tasks
state_store = JSONStateStore("/var/lib/state.json")
executor = SequentialExecutor(state_store=state_store)
executor.execute(workflow)  # Safe to interrupt and resume
```

**✗ Bad**: Non-idempotent tasks
```python
@task()
def increment_daily_counter():
    """NOT safe to resume - counter incremented twice"""
    db.execute("UPDATE counters SET count = count + 1")
    return db.query("SELECT count FROM counters")

# Resume will increment again (wrong!)
```

### 2. Explicit State Cleanup

**✓ Good**: Clear states when needed
```python
from flowweaver import JSONStateStore

state_store = JSONStateStore("/var/lib/state.json")

# Run workflow once
executor = SequentialExecutor(state_store=state_store)
executor.execute(workflow)

# Clear state for full re-run
state_store.clear_all_states()

# Run again (executes all tasks)
executor.execute(workflow)
```

**✗ Bad**: Stale states causing issues
```python
# State file has old results
# Running again loads stale data without realizing

# Could cause issues:
# - Old data cached from 2 weeks ago
# - Task never re-executes because marked COMPLETED
```

### 3. SQLite for Production, JSON for Development

**✓ Good**: Right tool for context
```python
import os

if os.getenv("ENVIRONMENT") == "production":
    # Production: indexed, queryable, ACID
    state_store = SQLiteStateStore("/var/lib/flowweaver/state.db")
else:
    # Development: human-readable, no dependencies
    state_store = JSONStateStore("/tmp/state.json")

executor = SequentialExecutor(state_store=state_store)
executor.execute(workflow)
```

**✗ Bad**: Using JSON in production
```python
# JSON fine for dev, but in production:
# - No indexing (slow queries)
# - No transactions (data corruption possible)
# - No concurrency control (WAL not available)

state_store = JSONStateStore("/var/lib/state.json")
executor = ThreadedExecutor(max_workers=10, state_store=state_store)
# High contention on concurrent writes
```

---

## Testing Strategies

### 1. Unit Test Task Functions

**✓ Good**: Test functions directly (decorator preserves callability)
```python
from flowweaver import task

@task()
def transform_user(user=None):
    # Decorated function
    if not user:
        raise ValueError("User required")
    
    return {
        "id": user["id"],
        "name": user["name"].upper()
    }

# Test directly (decorator doesn't break testing)
def test_transform_user():
    result = transform_user({"id": 1, "name": "alice"})
    assert result["name"] == "ALICE"

# Also works in workflow
def test_in_workflow():
    workflow = Workflow("test")
    workflow.add_task(transform_user)
    executor = SequentialExecutor()
    executor.execute(workflow)
    assert workflow.get_task("transform_user").status == TaskStatus.COMPLETED
```

### 2. Integration Test Workflows

**✓ Good**: Test workflows end-to-end
```python
import tempfile
from pathlib import Path

def test_workflow_execution():
    """Test complete workflow with state persistence"""
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "state.json"
        state_store = JSONStateStore(str(state_file))
        
        # Build test workflow
        workflow = Workflow("test")
        workflow.add_task(fetch_test_data)
        workflow.add_task(validate_test_data, depends_on=["fetch_test_data"])
        
        # Execute
        executor = SequentialExecutor(state_store=state_store)
        executor.execute(workflow)
        
        # Assert results
        assert workflow.tasks[0].status == TaskStatus.COMPLETED
        assert workflow.tasks[1].status == TaskStatus.COMPLETED
        
        # Verify state persisted
        assert state_file.exists()
```

### 3. Test Resumability

**✓ Good**: Test resume behavior
```python
def test_workflow_resumability():
    """Task not re-executed when resumed"""
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "state.json"
        state_store = JSONStateStore(str(state_file))
        
        call_count = 0
        
        def counted_task():
            nonlocal call_count
            call_count += 1
            return "result"
        
        # Run 1: Execute task
        workflow1 = Workflow("resume_test")
        workflow1.add_task(Task("task", counted_task))
        executor = SequentialExecutor(state_store=state_store)
        executor.execute(workflow1)
        
        assert call_count == 1  # Called once
        
        # Run 2: Resume workflow
        workflow2 = Workflow("resume_test")
        workflow2.add_task(Task("task", counted_task))
        executor2 = SequentialExecutor(state_store=state_store)
        executor2.execute(workflow2)
        
        assert call_count == 1  # NOT called again - restored from state!
```

---

## Monitoring & Observability

### 1. Structured Logging

**✓ Good**: Structured logs for querying
```python
import logging
import json

logger = logging.getLogger(__name__)

@task()
def process_batch(batch_id: str, data=None):
    logger.info(json.dumps({
        "event": "batch_processing_start",
        "batch_id": batch_id,
        "record_count": len(data) if data else 0
    }))
    
    try:
        result = process(data)
        
        logger.info(json.dumps({
            "event": "batch_processing_complete",
            "batch_id": batch_id,
            "result_count": len(result)
        }))
        
        return result
    
    except Exception as e:
        logger.error(json.dumps({
            "event": "batch_processing_error",
            "batch_id": batch_id,
            "error": str(e)
        }))
        raise
```

### 2. Task Callbacks for Monitoring

**✓ Good**: Use callbacks for side effects
```python
def on_task_complete(task: Task):
    """Called after task completes"""
    logger.info(f"Task {task.name} completed in {task.duration}s")
    
    # Send metric
    metrics.timer(f"task.{task.name}.duration", task.duration)

def on_task_error(task: Task, error: Exception):
    """Called on task failure"""
    logger.error(f"Task {task.name} failed: {error}")
    
    # Alert ops
    send_alert(f"Task failure: {task.name}", error)

@task(callbacks=[on_task_complete, on_task_error])
def important_task():
    return do_work()
```

---

## Common Pitfalls

### 1. Forgetting depends_on

**❌ Problem:**
```python
workflow.add_task(fetch)
workflow.add_task(process)  # Depends on fetch result but not declared
# May execute in wrong order or race condition
```

**✓ Solution:**
```python
workflow.add_task(fetch)
workflow.add_task(process, depends_on=["fetch"])  # Explicit!
```

### 2. Modifying External State in Tasks

**❌ Problem:**
```python
global_config = {}

@task()
def task_a():
    global_config["value"] = 1  # Modifies global state
    return global_config

@task()
def task_b():
    global_config["value"] = 2  # Race condition with task_a
    return global_config

# With ThreadedExecutor, results unpredictable
```

**✓ Solution:**
```python
@task()
def task_a():
    return {"value": 1}  # Return data, don't modify globals

@task()
def task_b():
    return {"value": 2}

# Use XCom pattern to pass data between tasks
```

### 3. Not Handling None in Context

**❌ Problem:**
```python
@task()
def process(upstream=None):
    return upstream["key"]  # KeyError if upstream is None
```

**✓ Solution:**
```python
@task()
def process(upstream=None):
    if not upstream:
        raise ValueError("upstream data required")
    
    return upstream.get("key", "default")
```

### 4. Ignoring Timeouts

**❌ Problem:**
```python
@task()  # No timeout - can hang forever
def unreliable_api_call():
    return requests.get(url, timeout=None).json()
```

**✓ Solution:**
```python
@task(timeout=30, retries=3)  # Timeout + retries
def unreliable_api_call():
    return requests.get(url, timeout=10).json()
```

---

## Summary Checklist

- [ ] **Design**: Focused workflows, explicit dependencies
- [ ] **Tasks**: Single responsibility, stateless, idempotent
- [ ] **Errors**: Retries for transient, timeouts for long-running
- [ ] **Performance**: Right executor, optimized thread pool
- [ ] **Data**: Type-hinted context, XCom pattern
- [ ] **Concurrency**: Thread-safe external access, avoid locks
- [ ] **Persistence**: Idempotent design, state store from start
- [ ] **Testing**: Unit test functions, integration test workflows
- [ ] **Monitoring**: Structured logs, task callbacks
- [ ] **Documentation**: Clear workflow purpose, task responsibilities

---

**Version**: 0.3.2 - Production Ready
**Last Updated**: February 2026
