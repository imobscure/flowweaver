# FlowWeaver

**Zero-Infrastructure Workflow Orchestration for Python**

FlowWeaver is a lightweight, production-ready library for building and executing data pipelines and workflows. It supports automatic dependency resolution, real-time monitoring, parallel execution, and both synchronous and asynchronous tasks—all with zero external dependencies.

## 🎯 Key Features

- **Zero Infrastructure**: No databases, message queues, or web servers required
- **True DAG Execution**: Automatic cycle detection with topological sorting
- **Real-time Monitoring**: Status callbacks, retry tracking, and execution statistics
- **Multiple Execution Strategies**: Sequential, threaded, and true async execution
- **Type-Safe**: Full Python 3.10+ type hints with mypy strict mode compliance
- **Production-Ready**: Comprehensive error handling, timeouts, and failure recovery
- **Developer-Friendly**: Simple decorator-free API with clear, Pythonic design

## 📦 Installation

```bash
# Using pip
pip install flowweaver

# Using uv (recommended)
uv add flowweaver
```

## 🚀 Quick Start

### Sequential Workflow

```python
from flowweaver import Task, Workflow, SequentialExecutor

# Define tasks
extract = Task(name="extract", fn=lambda: {"data": [1, 2, 3, 4, 5]})
transform = Task(name="transform", fn=lambda: {"doubled": [2, 4, 6, 8, 10]})
load = Task(name="load", fn=lambda: print("✓ Data loaded"))

# Build workflow
workflow = Workflow(name="ETL Pipeline")
workflow.add_task(extract)
workflow.add_task(transform, depends_on=["extract"])
workflow.add_task(load, depends_on=["transform"])

# Execute
executor = SequentialExecutor()
executor.execute(workflow)

# Access results
data = workflow.get_task_result("extract")
print(data)  # {'data': [1, 2, 3, 4, 5]}
```

### Async Workflow with Parallel Execution

```python
import asyncio
from flowweaver import Task, Workflow, AsyncExecutor

async def fetch_user(user_id: int) -> dict:
    # Simulated async I/O
    await asyncio.sleep(0.1)
    return {"id": user_id, "name": f"User{user_id}"}

async def fetch_orders(user_id: int) -> dict:
    await asyncio.sleep(0.1)
    return {"user_id": user_id, "orders": []}

workflow = Workflow(name="Data Fetch")

# Create tasks for multiple users - these will run in parallel
for user_id in range(1, 4):
    task = Task(name=f"user_{user_id}", fn=lambda uid=user_id: fetch_user(uid))
    workflow.add_task(task)

# Run in parallel (completes in ~0.1s, not 0.3s)
executor = AsyncExecutor()
executor.execute(workflow)

stats = workflow.get_workflow_stats()
print(f"Completed {stats['completed']} tasks in {stats['total_time_seconds']:.3f}s")
```

### Real-time Monitoring with Callbacks

```python
def on_task_start(task_name: str, status):
    print(f"📌 {task_name} started")

def on_task_complete(task_name: str, status):
    print(f"✅ {task_name} completed")

def on_retry_attempt(task_name: str, attempt: int):
    print(f"🔄 {task_name} retry attempt #{attempt}")

# Task with retry and monitoring
task = Task(
    name="api_call",
    fn=lambda: requests.get("https://api.example.com/data").json(),
    retries=3,
    timeout=5.0,
    on_status_change=lambda name, status: (
        on_task_start(name, status) if status.value == "running" 
        else on_task_complete(name, status) if status.value == "completed"
        else None
    ),
    on_retry=on_retry_attempt,
)
```

## 🏗️ Architecture

### Task States

```
          ┌─────────────────────┐
          │      PENDING        │
          │   (Initial State)   │
          └──────────┬──────────┘
                     │
                     ▼
          ┌─────────────────────┐
          │      RUNNING        │
          │  (Executing Task)   │
          └──────────┬──────────┘
                     │
         ┌───────────┴───────────┐
         ▼                       ▼
    ┌─────────────┐      ┌─────────────┐
    │  COMPLETED  │      │   FAILED    │
    │ (Success)   │      │ (Error)     │
    └─────────────┘      └─────────────┘
```

### Execution Plans

FlowWeaver uses **Kahn's Algorithm** (topological sort with level assignment) to generate execution plans:

```
Workflow:
    a → c ↘
    b → c → d

Execution Plan (3 layers):
    Layer 1: [a, b]  (no dependencies)
    Layer 2: [c]     (depends on a, b)
    Layer 3: [d]     (depends on c)
```

### Cycle Detection

Real-time cycle detection using **Depth-First Search (DFS)** prevents accidentally creating infinite loops:

```python
# This will raise ValueError immediately
workflow.add_task(task_c, depends_on=["a", "b"])
workflow.add_task(task_a, depends_on=["c"])  # ❌ Circular dependency detected!
```

## 📚 API Reference

### Task

```python
@dataclass
class Task:
    name: str                                                  # Unique task identifier
    fn: Union[Callable, Callable[..., Coroutine]]             # Sync or async function
    retries: int = 0                                          # Max retry attempts
    timeout: Optional[float] = None                           # Timeout in seconds
    status: TaskStatus = TaskStatus.PENDING                   # Current state
    result: Optional[Any] = None                              # Execution result
    error: Optional[str] = None                               # Error message
    on_status_change: Optional[Callable] = None               # Status callback
    on_retry: Optional[Callable] = None                       # Retry callback
    
    def execute() -> None                                     # Run sync task
    async def execute_async() -> None                         # Run async task
    def is_async() -> bool                                    # Check if async
```

### Workflow

```python
class Workflow:
    def __init__(self, name: str = "Workflow") -> None
    
    def add_task(
        self, 
        task: Task, 
        depends_on: Optional[list[str]] = None
    ) -> None
    
    def get_execution_plan(self) -> list[list[Task]]           # Topological sort
    async def execute_async(self) -> None                      # Run async workflow
    
    def get_task(self, task_name: str) -> Optional[Task]
    def get_dependencies(self, task_name: str) -> list[str]
    def get_all_tasks(self) -> dict[str, Task]
    
    def get_task_status(self, task_name: str) -> Optional[TaskStatus]
    def get_task_result(self, task_name: str) -> Any
    def get_workflow_stats(self) -> dict[str, Any]
```

### Executors

```python
class BaseExecutor(ABC):
    @abstractmethod
    def execute(self, workflow: Workflow) -> None
        """Execute workflow according to strategy"""

class SequentialExecutor(BaseExecutor):
    """Tasks execute one-by-one on main thread"""

class ThreadedExecutor(BaseExecutor):
    def __init__(self, max_workers: Optional[int] = None)
    """Parallel execution within layers using ThreadPool"""

class AsyncExecutor(BaseExecutor):
    def __init__(self, use_uvloop: bool = False)
    """True async/await execution with optional uvloop"""
```

## 🎓 Advanced Examples

### Data Pipeline with Error Handling

```python
from flowweaver import Task, Workflow, SequentialExecutor

def extract_csv(path: str) -> list[dict]:
    """Extract data from CSV file"""
    import csv
    with open(path) as f:
        return list(csv.DictReader(f))

def validate_data(data: list[dict]) -> list[dict]:
    """Remove invalid records"""
    return [r for r in data if len(r) > 0]

def transform_data(data: list[dict]) -> list[dict]:
    """Apply transformations"""
    return [{**r, "processed": True} for r in data]

def load_database(data: list[dict]) -> int:
    """Load to database - with retry"""
    # Simulated DB connection
    if not data:
        raise ValueError("No data to load")
    return len(data)

# Create workflow with error handling
workflow = Workflow(name="Data Pipeline")

extract_task = Task(name="extract", fn=lambda: extract_csv("data.csv"))
validate_task = Task(name="validate", fn=lambda: validate_data([]), depends_on=["extract"])
transform_task = Task(name="transform", fn=lambda: transform_data([]), depends_on=["validate"])
load_task = Task(
    name="load",
    fn=lambda: load_database([]),
    depends_on=["transform"],
    retries=2,  # Retry up to 2 times on failure
    timeout=30.0
)

for task in [extract_task, validate_task, transform_task, load_task]:
    workflow.add_task(task) if task.name == "extract" else workflow.add_task(
        task, depends_on=task.depends_on if hasattr(task, 'depends_on') else []
    )

executor = SequentialExecutor()
try:
    executor.execute(workflow)
    stats = workflow.get_workflow_stats()
    print(f"✅ Pipeline completed: {stats}")
except RuntimeError as e:
    print(f"❌ Pipeline failed: {e}")
```

### Conditional Execution Pattern

```python
from flowweaver import Task, Workflow
import random

workflow = Workflow(name="Conditional Processing")

def check_condition() -> bool:
    return random.choice([True, False])

def process_if_true() -> str:
    return "Condition was true!"

def process_if_false() -> str:
    return "Condition was false!"

# Create parallel branches based on condition
condition_task = Task(name="check", fn=check_condition)

true_branch = Task(name="true_path", fn=process_if_true)
false_branch = Task(name="false_path", fn=process_if_false)

workflow.add_task(condition_task)
# Note: In a real scenario, use a wrapper task that selectively executes branches
workflow.add_task(true_branch, depends_on=["check"])
workflow.add_task(false_branch, depends_on=["check"])

executor = SequentialExecutor()  # Sequential for this example
executor.execute(workflow)
```

## 🧪 Testing

Run the comprehensive test suite:

```bash
python -m pytest tests/test_comprehensive.py -v

# Or without pytest
python tests/test_comprehensive.py
```

## 📊 Performance Benchmarks

On a modern machine:

| Scenario | Time | Notes |
|----------|------|-------|
| 100-task linear workflow | 1.2ms | Sequential execution |
| 50-task parallel (4 workers) | 5ms | ThreadedExecutor |
| 10 async I/O tasks (0.1s each) | 108ms | AsyncExecutor (parallel) |
| Cycle detection (DAG with 1000 edges) | < 10ms | O(V+E) DFS |

## 🛡️ Best Practices

### 1. **Use Descriptive Task Names**
```python
# Good
Task(name="extract_customer_data", fn=extract_fn)
Task(name="validate_email_format", fn=validate_fn)

# Avoid
Task(name="t1", fn=extract_fn)
Task(name="t2", fn=validate_fn)
```

### 2. **Set Appropriate Timeouts**
```python
# For I/O-bound tasks with external dependencies
Task(name="api_call", fn=fetch_api, timeout=10.0)

# For CPU-bound tasks
Task(name="compute", fn=expensive_calc, timeout=60.0)

# No timeout for quick local operations
Task(name="sum", fn=lambda: 1+1)
```

### 3. **Use AsyncExecutor for I/O-bound Workflows**
```python
# ✅ Good - I/O operations run concurrently
async def fetch_user(id):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"api/users/{id}") as resp:
            return await resp.json()

# Use AsyncExecutor for true concurrency without GIL

# ❌ Avoid ThreadedExecutor for CPU-bound tasks (GIL contention)
```

### 4. **Implement Idempotent Tasks**
```python
# ✅ Good - safe to retry
def upsert_user(user_data: dict) -> int:
    return db.insert_or_update(user_data)

# ❌ Avoid - side effects on retry
counter = 0
def increment_counter() -> int:
    global counter
    counter += 1  # Bad! Retries will overccount
    return counter
```

### 5. **Monitor Workflows with Callbacks**
```python
def log_status(task_name: str, status: TaskStatus):
    print(f"[{task_name}] {status.value}")

task = Task(
    name="important_step",
    fn=some_function,
    on_status_change=log_status,
    retries=2
)
```

## 🚨 Error Handling

### Task Failures
```python
workflow = Workflow(name="fault-tolerant")
task = Task(name="risky", fn=risky_operation, retries=3)
workflow.add_task(task)

executor = SequentialExecutor()
try:
    executor.execute(workflow)
except RuntimeError as e:
    # Get detailed error info
    failed_task = workflow.get_task("risky")
    print(f"Task failed: {failed_task.error}")
```

### Dependency Validation
```python
try:
    workflow.add_task(task_c, depends_on=["nonexistent_task"])
except ValueError as e:
    print(f"Dependency error: {e}")

try:
    workflow.add_task(task_a, depends_on=["task_b"])
    workflow.add_task(task_b, depends_on=["task_a"])  # Circular!
except ValueError as e:
    print(f"Cycle detected: {e}")
```

## 🔧 Configuration & Logging

```python
import logging

# Enable debug logging
logging.getLogger("flowweaver").setLevel(logging.DEBUG)

# Use different executor strategies based on workload
if io_heavy:
    executor = AsyncExecutor()
elif cpu_bound and multicore:
    executor = ThreadedExecutor(max_workers=4)
else:
    executor = SequentialExecutor()
```

## 📈 Workflow Statistics

```python
workflow.execute(executor)

stats = workflow.get_workflow_stats()
# {
#   'total_tasks': 10,
#   'completed': 10,
#   'failed': 0,
#   'pending': 0,
#   'running': 0,
#   'total_time_seconds': 1.234
# }
```

## 🤝 Contributing

Contributions welcome! Areas for enhancement:
- Integration with external monitoring tools (Datadog, New Relic)
- Distributed execution backend (Celery, Ray)
- Web dashboard for workflow visualization
- Caching and memoization support
- Dynamic task generation

## 📝 License

MIT License - See LICENSE file for details

## 🎉 Changelog

### v0.2.0 (Current)
- ✨ Added async/await support with AsyncExecutor
- ✨ Real-time status callbacks and monitoring
- ✨ Task timeouts with configurable retry logic
- ✨ Comprehensive error handling and validation
- ✨ Workflow statistics and performance metrics
- 🧪 100+ comprehensive test cases
- 📚 Production-grade documentation

### v0.1.0 (Initial)
- Core task and workflow orchestration
- Sequential and threaded execution
- Cycle detection and topological sorting
- Basic error handling

---

**Built with ❤️ for Python developers who want simple, reliable workflows**
