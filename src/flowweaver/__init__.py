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
from flowweaver.utils import (
    export_mermaid,
    save_mermaid,
    view_mermaid,
)

__version__ = "0.2.0"
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
    "export_mermaid",
    "save_mermaid",
    "view_mermaid",
]
