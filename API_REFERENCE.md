# FlowWeaver v0.3.2 - Complete API Reference

## Table of Contents

1. [Core Classes](#core-classes)
2. [Decorators](#decorators)
3. [Executors](#executors)
4. [State Storage](#state-storage)
5. [Enums & Types](#enums--types)
6. [Exceptions](#exceptions)

---

## Core Classes

### `Workflow`

Main orchestration container for tasks. Manages task execution, data flow, and state.

#### Constructor
```python
Workflow(name: str, description: str = None)
```

**Parameters:**
- `name` (str, required): Unique workflow identifier
- `description` (str, optional): Human-readable description

**Example:**
```python
from flowweaver import Workflow

workflow = Workflow(
    name="data_pipeline",
    description="ETL pipeline for customer data"
)
```

#### Methods

##### `add_task(task_or_func: Union[Task, Callable], depends_on: List[str] = None) -> Task`

Add a task or decorated function to the workflow.

**Parameters:**
- `task_or_func` (Task or Callable): Task object or @task-decorated function
- `depends_on` (List[str], optional): List of upstream task names

**Returns:** Task object

**Example:**
```python
from flowweaver import Workflow, Task, task

workflow = Workflow("example")

# Method 1: Task object
def fetch_data():
    return {"count": 100}

workflow.add_task(
    Task("fetch", fetch_data),
    depends_on=[]
)

# Method 2: @task decorator
@task(retries=2)
def process_data(fetch=None):
    return {"processed": fetch["count"] * 2}

workflow.add_task(process_data, depends_on=["fetch"])
```

##### `execute(executor: BaseExecutor) -> None`

Execute workflow with specified executor.

**Parameters:**
- `executor` (BaseExecutor): Executor strategy (Sequential, Threaded, or Async)

**Raises:** `WorkflowExecutionError` if any task fails

**Example:**
```python
from flowweaver import SequentialExecutor

executor = SequentialExecutor()
workflow.execute(executor)
```

##### `get_task(name: str) -> Task`

Retrieve task by name.

**Returns:** Task object or `None` if not found

**Example:**
```python
task = workflow.get_task("fetch")
print(task.result)  # Access task result
```

##### `clear_results() -> None`

Clear all cached task results from memory.

**Example:**
```python
workflow.clear_results()  # Free memory after workflow completes
```

#### Properties

- `name` (str): Workflow name
- `description` (str): Workflow description
- `tasks` (list[Task]): List of all tasks in workflow
- `status` (WorkflowStatus): Overall workflow status

**Example:**
```python
print(f"Workflow: {workflow.name}")
print(f"Tasks: {len(workflow.tasks)}")
print(f"Status: {workflow.status}")
```

---

### `Task`

Individual unit of work within a workflow.

#### Constructor
```python
Task(
    name: str,
    func: Callable,
    retries: int = 0,
    timeout: float = None,
    callbacks: List[Callable] = None
)
```

**Parameters:**
- `name` (str, required): Unique task identifier
- `func` (Callable, required): Function to execute
- `retries` (int, default=0): Number of retry attempts on failure
- `timeout` (float, optional): Max seconds for task execution
- `callbacks` (List[Callable], optional): Functions to call after task completion

**Example:**
```python
from flowweaver import Task

def fetch_api():
    """Fetch data from API"""
    import requests
    return requests.get("https://api.example.com/data").json()

task = Task(
    name="api_fetch",
    func=fetch_api,
    retries=3,           # Retry 3 times on failure
    timeout=30,          # Max 30 seconds
    callbacks=[log_result]  # Call log_result after completion
)
```

#### Methods

##### `execute(context: Dict[str, Any] = None) -> Any`

Execute task with optional context (usually called by executors, not directly).

**Parameters:**
- `context` (dict, optional): Results from upstream tasks

**Returns:** Task result

**Raises:** `TaskExecutionError` if execution fails

**Example:**
```python
# Usually handled by executor, but can call directly:
result = task.execute(context={"upstream_task": {"data": 100}})
```

#### Properties

- `name` (str): Task name
- `status` (TaskStatus): Current execution status
- `result` (Any): Task output (only available after execution)
- `error` (Exception): Exception if task failed
- `retries` (int): Number of retry attempts configured

**Example:**
```python
from flowweaver import TaskStatus

task.execute()

if task.status == TaskStatus.COMPLETED:
    print(f"Result: {task.result}")
elif task.status == TaskStatus.FAILED:
    print(f"Error: {task.error}")
```

---

## Decorators

### `@task`

Decorator to convert plain functions into FlowWeaver tasks. Preserves original function callability for unit testing.

#### Syntax
```python
@task(name: str = None, retries: int = 0, timeout: float = None, callbacks: List[Callable] = None)
def my_function():
    ...
```

**Parameters:**
- `name` (str, optional): Override function name; defaults to function.__name__
- `retries` (int, default=0): Retry attempts on failure
- `timeout` (float, optional): Maximum execution time in seconds
- `callbacks` (List[Callable], optional): Post-completion callbacks

**Returns:** Original function with `__flowweaver__` metadata

**Key Feature**: Function remains callable for unit testing

**Example:**
```python
from flowweaver import task, Workflow

# Define decorated function
@task(retries=2, timeout=30)
def fetch_user(user_id: int):
    """Fetch user from database"""
    # This is a regular Python function
    return {"id": user_id, "name": f"User {user_id}"}

# Unit test (decorator preserves callability)
result = fetch_user(123)
assert result["name"] == "User 123"  # ✓ Works!

# Use in workflow
workflow = Workflow("user_pipeline")
workflow.add_task(fetch_user)  # Works with decorated functions
```

#### XCom Pattern (Context Injection)

Tasks can receive results from upstream tasks as keyword arguments:

```python
from flowweaver import task, Workflow, SequentialExecutor

@task()
def fetch_data():
    return {"user_id": 1, "name": "Alice"}

@task()
def process_data(fetch_data=None):  # Receives result of fetch_data
    # fetch_data contains: {"user_id": 1, "name": "Alice"}
    return {"processed": fetch_data["name"].upper()}

workflow = Workflow("example")
workflow.add_task(fetch_data)
workflow.add_task(process_data, depends_on=["fetch_data"])

executor = SequentialExecutor()
executor.execute(workflow)

print(workflow.get_task("process_data").result)
# Output: {"processed": "ALICE"}
```

---

## Executors

### BaseExecutor

Abstract base class for all executors. Define execution strategy.

#### Properties
- `state_store` (BaseStateStore, optional): Persistence backend for resumability

### SequentialExecutor

Execute tasks one at a time in dependency order. Best for CPU-bound work.

#### Constructor
```python
SequentialExecutor(state_store: BaseStateStore = None)
```

**Parameters:**
- `state_store` (BaseStateStore, optional): Persistence backend (defaults to None)

**Performance:**
- Execution Time: O(sum of all task durations)
- Memory: Minimal, results stored in memory + state_store
- Concurrency: None (strictly sequential)

**Example:**
```python
from flowweaver import Workflow, Task, SequentialExecutor, JSONStateStore

workflow = Workflow("sequential_example")
workflow.add_task(Task("step_1", lambda: 10))
workflow.add_task(Task("step_2", lambda: 20), depends_on=["step_1"])

# With persistence for resumability
state_store = JSONStateStore("/var/lib/flowweaver/state.json")
executor = SequentialExecutor(state_store=state_store)

executor.execute(workflow)
```

---

### ThreadedExecutor

Execute tasks in parallel using thread pool. Best for I/O-bound work.

#### Constructor
```python
ThreadedExecutor(
    max_workers: int = 4,
    state_store: BaseStateStore = None
)
```

**Parameters:**
- `max_workers` (int, default=4): Number of worker threads
- `state_store` (BaseStateStore, optional): Persistence backend

**Thread Safety:**
- Result store protected by `threading.RLock()`
- Context dict protected by `threading.RLock()`
- Safe for concurrent task execution

**Performance:**
- Execution Time: O(max(task durations)) + overhead
- Memory: Results + context dicts per thread
- Concurrency: Up to `max_workers` tasks in parallel

**Sizing Guide:**
```
For I/O-bound tasks: max_workers = (CPU cores * 2) to (CPU cores * 4)
For CPU-bound tasks: max_workers = CPU cores

Example:
  4-core machine, I/O-bound: max_workers=8-16
  4-core machine, CPU-bound: max_workers=4
```

**Example:**
```python
from flowweaver import Workflow, Task, ThreadedExecutor, JSONStateStore
import time

workflow = Workflow("parallel_io")

def fetch_url(url):
    import requests
    response = requests.get(url)
    return len(response.text)

for i in range(10):
    workflow.add_task(
        Task(f"fetch_{i}", lambda u=f"https://example.com/{i}": fetch_url(u))
    )

# Use thread pool for concurrent I/O
state_store = JSONStateStore("/var/lib/flowweaver/state.json")
executor = ThreadedExecutor(max_workers=8, state_store=state_store)

executor.execute(workflow)
```

---

### AsyncExecutor

Execute tasks concurrently using asyncio. Best for high-throughput async workloads.

#### Constructor
```python
AsyncExecutor(
    max_concurrent: int = 50,
    state_store: BaseStateStore = None
)
```

**Parameters:**
- `max_concurrent` (int, default=50): Max concurrent tasks
- `state_store` (BaseStateStore, optional): Persistence backend

**Usage:**
```python
from flowweaver import Workflow, Task, AsyncExecutor
import asyncio

async def main():
    workflow = Workflow("async_example")
    
    async def async_task():
        await asyncio.sleep(1)
        return "result"
    
    workflow.add_task(Task("async_1", async_task))
    
    executor = AsyncExecutor(max_concurrent=50)
    await executor.execute(workflow)

asyncio.run(main())
```

---

## State Storage

### BaseStateStore

Abstract base class for persistence backends.

#### Abstract Methods

```python
def save_task_state(
    task_name: str,
    status: TaskStatus,
    result: Any,
    error: Exception,
    timestamp: datetime
) -> None:
    """Persist completed task state"""
    ...

def load_task_state(task_name: str) -> Optional[Dict]:
    """Retrieve saved task state"""
    ...

def delete_task_state(task_name: str) -> None:
    """Remove saved task state"""
    ...

def list_all_tasks() -> List[str]:
    """List all saved task names"""
    ...

def clear_all_states() -> None:
    """Clear all saved states"""
    ...
```

---

### JSONStateStore

File-based state persistence using JSON with atomic writes.

#### Constructor
```python
JSONStateStore(
    store_path: str,
    pretty_print: bool = True
)
```

**Parameters:**
- `store_path` (str, required): Path to JSON file
- `pretty_print` (bool, default=True): Format output for readability

**Features:**
- Human-readable JSON format
- Atomic writes using temp file + rename
- Thread-safe with RLock
- No external dependencies

**Storage Format:**
```json
{
  "task_name": {
    "status": "COMPLETED",
    "result": {"key": "value"},
    "error": null,
    "timestamp": "2024-01-15T10:30:00"
  }
}
```

**Example:**
```python
from flowweaver import Workflow, Task, SequentialExecutor, JSONStateStore

workflow = Workflow("resumable_workflow")
workflow.add_task(Task("expensive", lambda: {"data": list(range(1000))}))

# Run 1: Execute and save state
store = JSONStateStore("/var/lib/state.json")
executor = SequentialExecutor(state_store=store)
executor.execute(workflow)

# Run 2: Automatically resumes from saved state
workflow2 = Workflow("resumable_workflow")
workflow2.add_task(Task("expensive", lambda: {"data": list(range(1000))}))

executor2 = SequentialExecutor(state_store=store)
executor2.execute(workflow2)  # Task not re-executed, result restored
```

---

### SQLiteStateStore

Database-backed state persistence with indexing and queries.

#### Constructor
```python
SQLiteStateStore(
    db_path: str,
    enable_gc: bool = True,
    gc_days: int = 30
)
```

**Parameters:**
- `db_path` (str, required): Path to SQLite database file
- `enable_gc` (bool, default=True): Auto-cleanup old records
- `gc_days` (int, default=30): Days of history to retain

**Features:**
- ACID transactions
- Indexed by task_name (fast lookup)
- Queryable task history
- Automatic garbage collection
- Concurrent write support via WAL mode

**Schema:**
```sql
CREATE TABLE tasks (
    task_name TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    result TEXT,
    error TEXT,
    timestamp DATETIME NOT NULL
);

CREATE INDEX idx_timestamp ON tasks(timestamp);
```

**Example:**
```python
from flowweaver import Workflow, Task, ThreadedExecutor, SQLiteStateStore
from datetime import datetime, timedelta

workflow = Workflow("production_workflow")
for i in range(100):
    workflow.add_task(Task(f"task_{i}", lambda i=i: {"result": i * 2}))

# Use SQLite for production (indexed, queryable)
store = SQLiteStateStore(
    "/var/lib/flowweaver/state.db",
    enable_gc=True,
    gc_days=30
)

executor = ThreadedExecutor(max_workers=4, state_store=store)
executor.execute(workflow)

# Query completed tasks
import sqlite3
conn = sqlite3.connect("/var/lib/flowweaver/state.db")
cursor = conn.cursor()

# Get all completed tasks
cursor.execute("SELECT task_name, timestamp FROM tasks WHERE status = 'COMPLETED'")
for task_name, timestamp in cursor.fetchall():
    print(f"{task_name}: {timestamp}")

conn.close()
```

---

## Enums & Types

### TaskStatus

Enumeration of task execution states.

```python
class TaskStatus(Enum):
    PENDING = "PENDING"        # Not yet executed
    RUNNING = "RUNNING"        # Currently executing
    COMPLETED = "COMPLETED"    # Finished successfully
    FAILED = "FAILED"          # Execution error
    RETRYING = "RETRYING"      # Retry in progress
    SKIPPED = "SKIPPED"        # Skipped due to dependency failure
```

**Example:**
```python
from flowweaver import Task, TaskStatus

task = Task("example", lambda: 42)
task.execute()

if task.status == TaskStatus.COMPLETED:
    print(f"✓ Success: {task.result}")
elif task.status == TaskStatus.FAILED:
    print(f"✗ Failed: {task.error}")
```

### WorkflowStatus

Enumeration of workflow execution states.

```python
class WorkflowStatus(Enum):
    IDLE = "IDLE"              # Not started
    RUNNING = "RUNNING"        # Executing tasks
    COMPLETED = "COMPLETED"    # All tasks finished
    FAILED = "FAILED"          # One or more tasks failed
```

---

## Exceptions

### WorkflowExecutionError

Raised when workflow execution fails.

```python
from flowweaver import Workflow, Task, SequentialExecutor, WorkflowExecutionError

workflow = Workflow("example")
workflow.add_task(Task("fail", lambda: 1/0))  # Division by zero

executor = SequentialExecutor()
try:
    executor.execute(workflow)
except WorkflowExecutionError as e:
    print(f"Workflow failed: {e}")
    print(f"Failed task: {e.failed_task}")
```

### TaskExecutionError

Raised when individual task execution fails.

```python
from flowweaver import Task, TaskExecutionError

def bad_task():
    raise ValueError("Intentional error")

task = Task("bad", bad_task)
try:
    task.execute()
except TaskExecutionError as e:
    print(f"Task failed: {e}")
    print(f"Original error: {e.__cause__}")
```

---

## Complete Example: Multi-Stage Pipeline

```python
from flowweaver import (
    Workflow,
    Task,
    task,
    ThreadedExecutor,
    SQLiteStateStore,
    TaskStatus
)

# Define tasks using @task decorator
@task(retries=2, timeout=30)
def fetch_raw_data():
    """Fetch data from multiple sources"""
    return {
        "users": [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}],
        "orders": [{"user_id": 1, "amount": 100}]
    }

@task(retries=1)
def validate_data(fetch_raw_data=None):
    """Validate data integrity"""
    if not fetch_raw_data:
        raise ValueError("No data to validate")
    
    assert isinstance(fetch_raw_data["users"], list)
    assert isinstance(fetch_raw_data["orders"], list)
    
    return {"valid": True, "record_count": len(fetch_raw_data["users"])}

@task()
def transform_data(
    fetch_raw_data=None,
    validate_data=None
):
    """Transform validated data"""
    if not validate_data["valid"]:
        raise ValueError("Data validation failed")
    
    transformed = {
        "user_count": len(fetch_raw_data["users"]),
        "order_count": len(fetch_raw_data["orders"]),
        "user_names": [u["name"] for u in fetch_raw_data["users"]]
    }
    
    return transformed

@task()
def load_to_warehouse(transform_data=None):
    """Load data to data warehouse"""
    print(f"Loading {transform_data['user_count']} users to warehouse")
    return {"rows_loaded": transform_data["user_count"]}

# Build workflow
workflow = Workflow(
    name="etl_pipeline",
    description="Extract, Transform, Load pipeline"
)

workflow.add_task(fetch_raw_data)
workflow.add_task(validate_data, depends_on=["fetch_raw_data"])
workflow.add_task(transform_data, depends_on=["fetch_raw_data", "validate_data"])
workflow.add_task(load_to_warehouse, depends_on=["transform_data"])

# Execute with state persistence
state_store = SQLiteStateStore("/var/lib/flowweaver/etl.db")
executor = ThreadedExecutor(max_workers=2, state_store=state_store)

try:
    executor.execute(workflow)
    
    # Check results
    for task in workflow.tasks:
        if task.status == TaskStatus.COMPLETED:
            print(f"✓ {task.name}: {task.result}")
        elif task.status == TaskStatus.FAILED:
            print(f"✗ {task.name}: {task.error}")
    
except Exception as e:
    print(f"Pipeline failed: {e}")
```

---

**Version**: 0.3.2 - Production Ready
**Last Updated**: February 2026
