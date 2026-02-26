"""FlowWeaver - Lightweight DAG-based workflow orchestration with production-grade features."""

from flowweaver.core import (
    Task,
    TaskStatus,
    Workflow,
    StateBackend,
    InMemoryStateBackend,
    task,
)
from flowweaver.executors import (
    BaseExecutor,
    SequentialExecutor,
    ThreadedExecutor,
    AsyncExecutor,
)
from flowweaver.storage import (
    BaseStateStore,
    JSONStateStore,
    SQLiteStateStore,
)

__version__ = "0.3.0"
__all__ = [
    "Task",
    "TaskStatus",
    "Workflow",
    "StateBackend",
    "InMemoryStateBackend",
    "task",
    "BaseExecutor",
    "SequentialExecutor",
    "ThreadedExecutor",
    "AsyncExecutor",
    "BaseStateStore",
    "JSONStateStore",
    "SQLiteStateStore",
]
