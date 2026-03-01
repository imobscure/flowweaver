# FlowWeaver v0.2.2 - Production Documentation Index

## Overview

Complete production documentation for FlowWeaver v0.2.2, the DAG-based workflow orchestration framework with built-in visualization.

**Status**: ✅ Production Ready  
**Version**: 0.2.2  
**Release Date**: March 2026  
**Python**: 3.9+

---

## Quick Start

If you're new to FlowWeaver, start here:

1. **[README.md](README.md)** - Overview and basic examples
2. **[API_REFERENCE.md](#api-reference)** - Core concepts and classes
3. **Run examples**: `python examples/parallel_run.py`

---

## Documentation Structure

### For Different Audiences

#### 👨‍💻 Developers Building Workflows
1. Start: [API_REFERENCE.md](#api-reference) - Core classes and decorators
2. Learn: [BEST_PRACTICES.md](#best-practices) - Design patterns
3. Explore: [examples/](examples/) directory - Working examples

#### 🚀 DevOps / SRE Deploying to Production
1. Start: [DEPLOYMENT_GUIDE.md](#deployment-guide) - Install and configure
2. Operate: [OPERATING_GUIDE.md](#operating-guide) - Run and monitor
3. Tune: [DEPLOYMENT_GUIDE.md#performance-tuning](#performance-tuning) - Optimize

#### 📊 Operations Team Running Workflows
1. Start: [OPERATING_GUIDE.md](#operating-guide) - Daily operations
2. Monitor: [OPERATING_GUIDE.md#monitoring-workflows](#monitoring-workflows)
3. Recover: [OPERATING_GUIDE.md#disaster-recovery](#disaster-recovery)

#### 🔍 Troubleshooting Issues
1. First check: [DEPLOYMENT_GUIDE.md#troubleshooting](#troubleshooting)
2. Then check: [OPERATING_GUIDE.md#troubleshooting-common-issues](#troubleshooting-common-issues)
3. Deep dive: [BEST_PRACTICES.md#common-pitfalls](#common-pitfalls)

---

## Documentation Files

### API_REFERENCE.md
**Comprehensive API documentation for all FlowWeaver classes and methods**

- **`Workflow`** - Main orchestration container
  - Constructor, methods (add_task, execute, get_task)
  - Properties (name, tasks, status)
  - Example: Multi-stage pipeline

- **`Task`** - Individual units of work
  - Constructor, execute method
  - Properties (status, result, error)
  - Example: Creating and running tasks

- **`@task` decorator** - Convert functions to tasks
  - Syntax, parameters
  - XCom pattern for data flow
  - Unit testing decorated functions

- **Executors** - Execution strategies
  - **SequentialExecutor** - One at a time (CPU-bound)
  - **ThreadedExecutor** - Parallel threads (I/O-bound)
  - **AsyncExecutor** - Async/await (high-throughput)
  - Performance characteristics and sizing

- **State Storage** - Persistence backends
  - **BaseStateStore** - Abstract interface
  - **JSONStateStore** - File-based, human-readable
  - **SQLiteStateStore** - Database, indexed, ACID

- **Enums** - TaskStatus, WorkflowStatus
- **Exceptions** - WorkflowExecutionError, TaskExecutionError
- **Visualization Utilities** - Mermaid.js DAG export, save, and browser preview

**When to use**: Building workflows, understanding API

---

### DEPLOYMENT_GUIDE.md
**Complete guide to installing and deploying FlowWeaver to production**

**Sections:**

1. **Installation** - Install FlowWeaver and dependencies
2. **Environment Setup** - Python version, virtual environments
3. **Deployment Checklist** - Pre/post deployment verification
4. **Configuration**
   - Executor selection (which one for your workload?)
   - ThreadedExecutor sizing
   - AsyncExecutor setup
   - State store choice (JSON vs SQLite)
5. **Health Checks** - Health endpoint implementation
6. **Metrics** - What to monitor and targets
7. **Logging & Debugging** - Configure and debug workflows
8. **Troubleshooting**
   - Task resumation issues
   - Race conditions
   - Memory leaks
   - Timeouts
   - Database locks
9. **Production Checklist** - Final verification before go-live

**Example sections**: Health check API, metrics collection, state store recovery

**When to use**: First-time deployment, setup verification, production configuration

---

### OPERATING_GUIDE.md
**Daily operations and troubleshooting for running FlowWeaver workflows**

**Sections:**

1. **Starting & Stopping Workflows**
   - WorkflowRunner class for scripted execution
   - Running via Cron
   - Running via Systemd
   - Example customer pipeline

2. **Monitoring Workflows**
   - Health check endpoints
   - Prometheus metrics format
   - Checking task status via SQL
   - Monitoring via logs

3. **Troubleshooting Common Issues**
   - Workflow hanging
   - High CPU usage
   - State store locked/corrupted
   - Diagnostic commands

4. **Performance Tuning**
   - Thread pool sizing guide
   - State store performance
   - Task batching strategy

5. **Disaster Recovery**
   - Backup procedures
   - Restore from backup
   - Recovery if state lost
   - Rebuilding from external sources

6. **Upgrading FlowWeaver**
   - Check version
   - Upgrade process
   - Backward compatibility

7. **Operational Runbooks**
   - Handle failed task
   - Restart failed workflow

**When to use**: Daily operations, troubleshooting, maintenance

---

### BEST_PRACTICES.md
**Production-grade design patterns and recommendations**

**Sections:**

1. **Workflow Design**
   - Keep workflows focused
   - Explicit dependency declaration
   - Design for resumability

2. **Task Design**
   - Single responsibility per task
   - Stateless tasks
   - Proper function signatures for XCom
   - Meaningful names

3. **Error Handling & Resilience**
   - Use retries for transient failures
   - Set timeouts
   - Explicit error handling

4. **Performance Optimization**
   - Choose right executor
   - Thread pool sizing
   - Batch small tasks
   - Use state store for large results

5. **Data Flow & Context**
   - Leverage XCom pattern
   - Type your context
   - Example: Join data from multiple sources

6. **Concurrency & Thread Safety**
   - ThreadedExecutor thread safety (automatic)
   - Protecting external shared state
   - Avoiding locks in task functions

7. **Persistence & Resumability**
   - Design for resumability from day one
   - Explicit state cleanup
   - SQLite for production, JSON for development

8. **Testing Strategies**
   - Unit test task functions
   - Integration test workflows
   - Test resumability

9. **Monitoring & Observability**
   - Structured logging
   - Task callbacks

10. **Common Pitfalls**
    - Forgetting depends_on
    - Modifying external state
    - Not handling None in context
    - Ignoring timeouts

**When to use**: Designing workflows, avoiding mistakes, architectural decisions

---

## Feature Documentation

### Mermaid.js Visualization (v0.2.0)

FlowWeaver v0.2.0 includes built-in DAG visualization:

**Functions:**
- `export_mermaid(workflow, orientation)` — Returns Mermaid graph string
- `save_mermaid(workflow, filepath, orientation)` — Writes Mermaid to a file
- `view_mermaid(workflow, orientation)` — Opens interactive HTML diagram in browser

**Status colours:**
- COMPLETED = green (`#28a745`)
- FAILED = red (`#dc3545`)
- RUNNING = orange (`#fd7e14`)
- PENDING = grey (`#6c757d`)

**Location in code:**
- [src/flowweaver/utils.py](src/flowweaver/utils.py) — Full visualization module

**Usage:**
See [API_REFERENCE.md#visualization-utilities](#visualization-utilities) and [examples/visualize_dag.py](examples/visualize_dag.py)

---

### Thread Safety

FlowWeaver includes explicit thread-safe locking:

**Components:**
- `Workflow._result_store` protected by RLock
- `ThreadedExecutor` context dict protected by RLock
- All state store operations thread-safe

**Location in code:**
- [src/flowweaver/core.py](src/flowweaver/core.py#L320-L321) - Result store and lock
- [src/flowweaver/executors.py](src/flowweaver/executors.py#L16-L30) - Thread safety initialization
- [src/flowweaver/executors.py](src/flowweaver/executors.py#L234-L236) - ThreadedExecutor context lock

**Usage:**
See [BEST_PRACTICES.md#concurrency--thread-safety](#concurrency--thread-safety)

---

### Resumability

Tasks can resume from state store on restart - no re-execution:

**How it works:**
1. Task completes → result saved to state store
2. Workflow interrupted/restarted
3. Executor checks state store before executing task
4. Task restored from store → zero re-execution

**Components:**
- `BaseExecutor._restore_task_from_store()` - Check state before execution
- `BaseExecutor._save_task_to_store()` - Persist after success
- All three executors integrated with resumability check

**Location in code:**
- [src/flowweaver/executors.py](src/flowweaver/executors.py#L73-L127) - BaseExecutor methods
- [src/flowweaver/executors.py](src/flowweaver/executors.py#L186-L190) - SequentialExecutor integration
- [src/flowweaver/executors.py](src/flowweaver/executors.py#L311-L319) - ThreadedExecutor integration
- [src/flowweaver/executors.py](src/flowweaver/executors.py#L470-L481) - AsyncExecutor integration

**Usage:**
See [DEPLOYMENT_GUIDE.md#state-store-configuration](#state-store-configuration)

---

### XCom Pattern (Data Flow)

Tasks pass data to dependent tasks via context injection:

**How it works:**
```python
@task()
def upstream():
    return {"data": "value"}

@task()
def downstream(upstream=None):  # Receives result of upstream via **kwargs
    return {"processed": upstream["data"]}
```

**Components:**
- `Workflow._build_context_for_task()` - Builds context from dependencies
- Task parameters matched to dependency results
- All executors build and inject context

**Location in code:**
- [src/flowweaver/core.py](src/flowweaver/core.py#L595-L620) - Context building
- [src/flowweaver/executors.py](src/flowweaver/executors.py#L160-L175) - Context injection in SequentialExecutor

**Usage:**
See [API_REFERENCE.md#task-decorator](#task-decorator) and [BEST_PRACTICES.md#data-flow--context](#data-flow--context)

---

## Examples

Located in [examples/](examples/) directory:

- **[examples/parallel_run.py](examples/parallel_run.py)** — ThreadedExecutor with parallel tasks
- **[examples/ml_pipeline.py](examples/ml_pipeline.py)** — ML workflow example
- **[examples/etl_pipeline.py](examples/etl_pipeline.py)** — ETL workflow example
- **[examples/async_aggregation.py](examples/async_aggregation.py)** — Async workflow example
- **[examples/complex_workflow.py](examples/complex_workflow.py)** — Multi-stage DAG demo
- **[examples/full_run.py](examples/full_run.py)** — Complete end-to-end run
- **[examples/visualize_dag.py](examples/visualize_dag.py)** — Mermaid.js visualization demo

**Running examples:**
```bash
python examples/parallel_run.py
python examples/visualize_dag.py
```

---

## Testing

### Test Files

- **[tests/test_core.py](tests/test_core.py)** — Core Task, Workflow, and DAG tests
- **[tests/test_comprehensive.py](tests/test_comprehensive.py)** — Full feature and executor tests
- **[tests/test_real_world.py](tests/test_real_world.py)** — Real-world workflow patterns
- **[tests/test_stress.py](tests/test_stress.py)** — Stress and performance tests

**Running tests:**
```bash
pytest tests/ -v
```

---

## Architecture Overview

### Core Components

```
Workflow (orchestration container)
  ├── Tasks (units of work)
  ├── State (result store + threading locks)
  └── Executor (execution strategy)
        ├── SequentialExecutor (single thread)
        ├── ThreadedExecutor (thread pool)
        └── AsyncExecutor (async/await)

StateStore (persistence layer)
  ├── JSONStateStore (file-based)
  └── SQLiteStateStore (database)
```

### Execution Flow

```
1. Workflow.add_task() - Define tasks and dependencies
2. Executor.execute(workflow) - Start execution
3. For each task:
   a. executor._restore_task_from_store() - Check if already done
   b. If yes: restore result, skip execution
   c. If no: build context, execute task function
   d. executor._save_task_to_store() - Save result
   e. Store result in workflow._result_store (with RLock)
4. Return completed workflow
```

### Thread Safety

```
ThreadedExecutor
  ├── Multiple threads execute tasks in parallel
  ├── Each task result stored in _result_store (RLock protected)
  ├── Context dict updates protected by RLock
  └── All state store operations thread-safe
```

---

## Common Tasks

### I want to...

**Build a workflow**
→ [API_REFERENCE.md#complete-example-multi-stage-pipeline](#complete-example-multi-stage-pipeline)

**Deploy to production**
→ [DEPLOYMENT_GUIDE.md](#deployment-guide)

**Handle failures gracefully**
→ [BEST_PRACTICES.md#error-handling--resilience](#error-handling--resilience)

**Monitor running workflows**
→ [OPERATING_GUIDE.md#monitoring-workflows](#monitoring-workflows)

**Optimize performance**
→ [BEST_PRACTICES.md#performance-optimization](#performance-optimization) + [DEPLOYMENT_GUIDE.md#performance-tuning](#performance-tuning)

**Debug a failed task**
→ [DEPLOYMENT_GUIDE.md#logging--debugging](#logging--debugging)

**Resume from interruption**
→ [DEPLOYMENT_GUIDE.md#state-store-configuration](#state-store-configuration)

**Handle thread safety**
→ [BEST_PRACTICES.md#concurrency--thread-safety](#concurrency--thread-safety)

**Visualise a workflow DAG**
→ [API_REFERENCE.md#visualization-utilities](#visualization-utilities)

**Migrate from another framework**
→ [examples/](examples/) - See conversion strategies

---

## Command Reference

### Unit Test Tasks
```bash
# Test task function directly (decorator preserves callability)
@task()
def my_task():
    ...

result = my_task()  # Works!
```

### Run Workflow
```python
from flowweaver import Workflow, SequentialExecutor

executor = SequentialExecutor()
executor.execute(workflow)
```

### Persist State
```python
from flowweaver import SQLiteStateStore

state_store = SQLiteStateStore("state.db")
executor = SequentialExecutor(state_store=state_store)
```

### Check Task Status
```bash
sqlite3 state.db "SELECT task_name, status FROM tasks;"
```

### Monitor Health
```bash
curl http://localhost:5000/health
```

---

## Support & Resources

- **Issues**: https://github.com/imobscure/flowweaver/issues
- **Discussions**: https://github.com/imobscure/flowweaver/discussions

---

## Version History

### v0.2.2 (Current) - March 2026
✅ Production Ready

**New:**
- Resiliency at scale — corrupted JSON state files handled gracefully
- Chain-based visualization — Mermaid.js supports 5,000+ task DAGs
- CI test matrix across Python 3.9–3.12
- CHANGELOG.md

### v0.2.0 - February 2026

**New:**
- Mermaid.js DAG visualization (`export_mermaid`, `save_mermaid`, `view_mermaid`)
- Interactive browser-based workflow diagrams with colour-coded task statuses
- Fixed async executor context injection
- 7 example scripts including visualization demo

**Improved:**
- Comprehensive production documentation (all docs updated to v0.2.0)
- 31 passing tests across 4 test files

### v0.1.0 - Initial
- Core task and workflow orchestration
- Sequential, threaded, and async execution
- Cycle detection and topological sorting
- JSONStateStore and SQLiteStateStore persistence
- XCom data flow pattern

---

## Summary

FlowWeaver v0.2.0 is a **production-ready workflow orchestration framework** with:

✅ **Three core execution strategies** — Sequential, Threaded, Async  
✅ **Built-in DAG visualization** — Mermaid.js with colour-coded task statuses  
✅ **Pluggable persistence** — JSON or SQLite state stores  
✅ **Thread-safe operations** — Explicit RLock protection  
✅ **Resumable workflows** — Skip completed tasks on restart  
✅ **Clean API** — @task decorators that preserve testability  
✅ **Professional documentation** — Deployment, operations, best practices  

**Get started**: Start with examples, then review API_REFERENCE.md for your use case.

**Deploy production**: Follow DEPLOYMENT_GUIDE.md + BEST_PRACTICES.md.

**Operate safely**: Use OPERATING_GUIDE.md + health monitoring.

---

**Documentation Version**: 0.2.2  
**Last Updated**: March 2026  
**Status**: Complete and Production Ready ✅
