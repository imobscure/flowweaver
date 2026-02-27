# FlowWeaver v0.3.2 - Production Deployment Guide

## Table of Contents
1. [Installation](#installation)
2. [Environment Setup](#environment-setup)
3. [Deployment Checklist](#deployment-checklist)
4. [Configuration](#configuration)
5. [Monitoring & Health Checks](#monitoring--health-checks)
6. [Logging & Debugging](#logging--debugging)
7. [Troubleshooting](#troubleshooting)

---

## Installation

### 1. Install FlowWeaver
```bash
# From PyPI (when published)
pip install flowweaver

# Or from source
git clone https://github.com/your-org/flowweaver.git
cd flowweaver
pip install -e .
```

### 2. Verify Installation
```python
from flowweaver import Workflow, Task, SequentialExecutor
print("✓ FlowWeaver installed successfully")
```

---

## Environment Setup

### Python Version
- **Minimum**: Python 3.10
- **Recommended**: Python 3.11 or 3.12

### Virtual Environment (Strongly Recommended)
```bash
# Create isolated environment
python -m venv flowweaver-env

# Activate
# On Linux/Mac:
source flowweaver-env/bin/activate
# On Windows:
flowweaver-env\Scripts\activate

# Install FlowWeaver
pip install flowweaver
```

### Production Dependencies
```bash
# Core requirements (installed automatically)
# flowweaver requires: Python 3.10+
# No external dependencies for core library

# Optional: State persistence backends
pip install flowweaver[sqlite]   # For SQLiteStateStore
pip install flowweaver[aws]      # For cloud storage (future)
```

### Production Environment Variables
```bash
# Logging configuration
export FLOWWEAVER_LOG_LEVEL=INFO          # DEBUG, INFO, WARNING, ERROR, CRITICAL
export FLOWWEAVER_LOG_FILE=/var/log/flowweaver.log

# State store configuration
export FLOWWEAVER_STATE_STORE=sqlite      # json, sqlite
export FLOWWEAVER_STATE_PATH=/var/lib/flowweaver/state.db

# Performance tuning
export FLOWWEAVER_THREAD_POOL_SIZE=4      # For ThreadedExecutor
export FLOWWEAVER_TASK_TIMEOUT=3600       # Seconds per task max
```

---

## Deployment Checklist

### Pre-Deployment Verification

- [ ] Python version ≥ 3.10: `python --version`
- [ ] All tests pass: `pytest tests/ -v`
- [ ] Smoke tests pass: `python smoke_test.py`
- [ ] SDE-2 validation passes: `python test_sde2_complete.py`
- [ ] Code linting passes: `pylint src/flowweaver/`
- [ ] Type checking passes: `mypy src/flowweaver/`
- [ ] No security vulnerabilities: `pip-audit`

### Deployment Steps

```bash
# 1. Verify environment
python -c "from flowweaver import Workflow; print('✓ Ready')"

# 2. Set up state storage
mkdir -p /var/lib/flowweaver
chmod 755 /var/lib/flowweaver

# 3. Configure logging
mkdir -p /var/log/flowweaver
chmod 755 /var/log/flowweaver

# 4. Deploy code
# Copy src/flowweaver/ to production location

# 5. Run final smoke test
python -m pytest smoke_test.py -v

# 6. Deploy application using FlowWeaver
# (See examples in examples/ directory)

# 7. Monitor health
python -c "from flowweaver import Workflow; w = Workflow('health'); print('✓ Healthy')"
```

### Post-Deployment Validation

```bash
# Health check endpoint
curl http://localhost:8000/health    # If exposing via service

# State store verification
python -c "from flowweaver import JSONStateStore; \
           store = JSONStateStore('/var/lib/flowweaver/state.json'); \
           print('✓ State store accessible')"

# Task execution test
python examples/parallel_run.py      # Run example workflow
```

---

## Configuration

### Executor Selection

| Executor | Use Case | Scale |
|----------|----------|-------|
| **SequentialExecutor** | CPU-bound, deterministic | Small (1-10 tasks) |
| **ThreadedExecutor** | I/O-bound, high concurrency | Medium (10-100 tasks) |
| **AsyncExecutor** | Async/await workloads | Large (100+ tasks) |

### Executor Configuration

#### SequentialExecutor (Default)
```python
from flowweaver import Workflow, SequentialExecutor

workflow = Workflow("my_workflow")
# Add tasks...

executor = SequentialExecutor()
executor.execute(workflow)
```

#### ThreadedExecutor (For I/O-bound tasks)
```python
from flowweaver import Workflow, ThreadedExecutor

workflow = Workflow("io_workflow")
# Add tasks...

# Configure thread pool size based on I/O bound tasks
# Rule of thumb: (cores * 2) to (cores * 4)
executor = ThreadedExecutor(max_workers=8)
executor.execute(workflow)
```

#### AsyncExecutor (For async operations)
```python
from flowweaver import Workflow, AsyncExecutor
import asyncio

async def main():
    workflow = Workflow("async_workflow")
    # Add tasks...
    
    executor = AsyncExecutor(max_concurrent=50)
    await executor.execute(workflow)

asyncio.run(main())
```

### State Store Configuration

#### JSONStateStore (File-based, Human-readable)
```python
from flowweaver import Workflow, SequentialExecutor, JSONStateStore

workflow = Workflow("my_workflow")
# Add tasks...

# Create state store with atomic writes
state_store = JSONStateStore("/var/lib/flowweaver/state.json")

executor = SequentialExecutor(state_store=state_store)
executor.execute(workflow)
```

#### SQLiteStateStore (Database, Indexed, Queryable)
```python
from flowweaver import Workflow, ThreadedExecutor, SQLiteStateStore

workflow = Workflow("my_workflow")
# Add tasks...

# SQLite database for production (indexed queries, ACID transactions)
state_store = SQLiteStateStore("/var/lib/flowweaver/state.db")

executor = ThreadedExecutor(max_workers=4, state_store=state_store)
executor.execute(workflow)
```

---

## Monitoring & Health Checks

### Health Check Implementation

```python
#!/usr/bin/env python3
"""Health check endpoint for production monitoring"""

from flowweaver import Workflow, Task, SequentialExecutor, JSONStateStore
from datetime import datetime
import json

def health_check():
    """Returns system health status"""
    try:
        # Test 1: Core imports
        from flowweaver import Workflow, Task
        
        # Test 2: State store accessibility
        state_store = JSONStateStore("/var/lib/flowweaver/state.json")
        
        # Test 3: Simple task execution
        def dummy_task():
            return {"status": "ok"}
        
        workflow = Workflow("health_check")
        workflow.add_task(Task("dummy", dummy_task))
        
        executor = SequentialExecutor(state_store=state_store)
        executor.execute(workflow)
        
        if workflow.tasks[0].status.name != "COMPLETED":
            return {"status": "unhealthy", "reason": "task failed"}
        
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "version": "0.3.2",
            "checks": {
                "imports": "ok",
                "state_store": "ok",
                "execution": "ok"
            }
        }
    
    except Exception as e:
        return {
            "status": "unhealthy",
            "reason": str(e),
            "timestamp": datetime.now().isoformat()
        }

if __name__ == "__main__":
    health = health_check()
    print(json.dumps(health, indent=2))
    exit(0 if health["status"] == "healthy" else 1)
```

### Metrics to Monitor

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| Task Completion Rate | ≥ 99.5% | < 99% |
| Avg Task Duration | < 10ms | > 30ms (p99) |
| State Store Latency | < 5ms | > 20ms |
| Memory per Task | < 50MB | > 100MB |
| Thread Pool Utilization | 60-80% | > 90% |

### Monitoring Code Example

```python
import time
import json
from datetime import datetime
from flowweaver import Workflow, Task, ThreadedExecutor, JSONStateStore

class MetricsCollector:
    def __init__(self):
        self.task_times = {}
        self.state_store_times = {}
    
    def track_task_duration(self, task_name, duration):
        if task_name not in self.task_times:
            self.task_times[task_name] = []
        self.task_times[task_name].append(duration)
    
    def track_state_store_operation(self, operation, duration):
        if operation not in self.state_store_times:
            self.state_store_times[operation] = []
        self.state_store_times[operation].append(duration)
    
    def get_metrics(self):
        """Returns current metrics"""
        import statistics
        
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "task_durations": {},
            "state_store_latency": {}
        }
        
        for task_name, durations in self.task_times.items():
            metrics["task_durations"][task_name] = {
                "avg_ms": statistics.mean(durations) * 1000,
                "p99_ms": sorted(durations)[int(len(durations) * 0.99)] * 1000,
                "count": len(durations)
            }
        
        for op, durations in self.state_store_times.items():
            metrics["state_store_latency"][op] = {
                "avg_ms": statistics.mean(durations) * 1000,
                "p99_ms": sorted(durations)[int(len(durations) * 0.99)] * 1000,
                "count": len(durations)
            }
        
        return metrics

# Usage
collector = MetricsCollector()

# Your workflow execution...
start = time.time()
# task execution
end = time.time()
collector.track_task_duration("my_task", end - start)

# Get metrics
print(json.dumps(collector.get_metrics(), indent=2))
```

---

## Logging & Debugging

### Configure Logging

```python
import logging
import sys

# Set up logging for production
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/flowweaver/flowweaver.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger('flowweaver')
logger.info("FlowWeaver initialized")
```

### Debug Task Execution

```python
from flowweaver import Workflow, Task, SequentialExecutor, TaskStatus

workflow = Workflow("debug_test")

def failing_task():
    raise ValueError("Intentional error for debugging")

workflow.add_task(Task("debug", failing_task))

executor = SequentialExecutor()
executor.execute(workflow)

# Inspect task status and errors
task = workflow.tasks[0]
print(f"Task Status: {task.status}")
print(f"Task Result: {task.result}")
print(f"Task Error: {task.error if task.status == TaskStatus.FAILED else 'None'}")
```

### Debug Resumability

```python
from flowweaver import Workflow, Task, SequentialExecutor, JSONStateStore

state_dir = "/var/lib/flowweaver"
state_store = JSONStateStore(f"{state_dir}/debug_state.json")

workflow = Workflow("resume_debug")
workflow.add_task(Task("expensive", lambda: {"data": "result"}))

# Run 1: Execute and save state
executor = SequentialExecutor(state_store=state_store)
executor.execute(workflow)

print("Run 1 - Task executed")
print(f"State store file: {state_store.store_path}")

# Run 2: Resume from state
workflow2 = Workflow("resume_debug")
workflow2.add_task(Task("expensive", lambda: {"data": "result"}))

executor2 = SequentialExecutor(state_store=state_store)
executor2.execute(workflow2)

print("Run 2 - Task restored from state (not re-executed)")
```

---

## Troubleshooting

### Issue: Tasks Not Resuming from State Store

**Symptom**: workflow re-executes all tasks on second run despite state store

**Causes**:
1. State store path not writable
2. Different workflow/task names between runs
3. Task state corrupted

**Solution**:
```bash
# Verify state store permissions
ls -la /var/lib/flowweaver/
chmod 755 /var/lib/flowweaver/

# Check state store content
cat /var/lib/flowweaver/state.json | json_pp

# Or query SQLite
sqlite3 /var/lib/flowweaver/state.db "SELECT * FROM tasks LIMIT 10;"
```

### Issue: ThreadedExecutor Race Conditions

**Symptom**: Inconsistent results when using ThreadedExecutor

**Cause**: Not using explicit RLock (v0.3.2 includes RLock protection)

**Solution**:
```python
from flowweaver import ThreadedExecutor

# v0.3.2+ automatically uses RLock for thread safety
executor = ThreadedExecutor(max_workers=4)
# RLock is automatically configured
```

### Issue: Memory Leak with Large Workflows

**Symptom**: Memory usage grows unbounded with 1000+ tasks

**Solution**:
```python
from flowweaver import Workflow, Task, SequentialExecutor, JSONStateStore

# Use state store to periodically clear result_store
state_store = JSONStateStore("/var/lib/flowweaver/state.json")

workflow = Workflow("large_workflow")
# Add 1000+ tasks...

executor = SequentialExecutor(state_store=state_store)
executor.execute(workflow)

# State store persists results to disk (reduces memory footprint)
# Completed tasks: results in state store, not memory
```

### Issue: Timeout on Long-Running Tasks

**Symptom**: Task execution hangs or times out

**Solution**:
```python
from flowweaver import Task

# Specify timeout per task (seconds)
task = Task(
    "long_task",
    lambda: heavy_computation(),
    timeout=600  # 10 minutes
)
```

### Issue: State Store Database Locked

**Symptom**: "database is locked" error with SQLiteStateStore

**Solution**:
```python
from flowweaver import SQLiteStateStore

# SQLiteStateStore uses WAL mode for concurrent access
# If still locking, reduce concurrent executors:
# - Instead of 4 threads, use 2
# - Or use JSONStateStore for very high concurrency

# Check database integrity
# sqlite3 /var/lib/flowweaver/state.db "PRAGMA integrity_check;"
```

---

## Production Checklist

- [ ] Python 3.10+ installed and verified
- [ ] FlowWeaver installed from package
- [ ] All tests pass in production environment
- [ ] State store directory created and permissions set
- [ ] Log directory created and permissions set
- [ ] Environment variables configured
- [ ] Health check endpoint deployed
- [ ] Monitoring metrics configured
- [ ] Alerting thresholds set
- [ ] Backup strategy for state store configured
- [ ] Log rotation configured
- [ ] Security: FlowWeaver process runs with minimal privileges
- [ ] Capacity planning: Thread pool size matches workload
- [ ] Disaster recovery plan documented

---

## Support & Resources

- **Documentation**: See [API_REFERENCE.md](API_REFERENCE.md)
- **Examples**: See [examples/](examples/) directory
- **Best Practices**: See [BEST_PRACTICES.md](BEST_PRACTICES.md)
- **Issues**: https://github.com/your-org/flowweaver/issues
- **Version**: 0.3.2 - Production Ready
