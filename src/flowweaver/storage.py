
import json
import sqlite3
import threading
from threading import RLock
import time
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, TYPE_CHECKING

from .core import TaskStatus

if TYPE_CHECKING:
    from .core import Workflow


class BaseStateStore(ABC):
    """
    Abstract base class for task state persistence backends.

    Implementations must handle:
    - Atomic save/load operations
    - Thread safety for concurrent access
    - Error handling for IO failures

    Example:
        backend = JSONStateStore("workflow_state.json")
        backend.save_task_state("task_1", TaskStatus.COMPLETED, result=42)
        state = backend.load_task_state("task_1")
    """

    @abstractmethod
    def save_task_state(
        self,
        task_name: str,
        status: TaskStatus,
        result: Any = None,
        error: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """
        Save task execution state to persistent storage.

        Args:
            task_name: Unique identifier for the task.
            status: Current TaskStatus (RUNNING, COMPLETED, FAILED, etc).
            result: Task execution result (if any).
            error: Error message (if task failed).
            timestamp: Execution timestamp (defaults to now).

        Raises:
            IOError: If write operation fails.
        """
        pass

    @abstractmethod
    def load_task_state(self, task_name: str) -> Optional[Dict[str, Any]]:
        """
        Load task execution state from persistent storage.

        Args:
            task_name: Unique identifier for the task.

        Returns:
            Dict with keys: status, result, error, timestamp
            Returns None if task state not found.

        Raises:
            IOError: If read operation fails.
        """
        pass

    @abstractmethod
    def clear_task_state(self, task_name: str) -> None:
        """
        Delete task state from persistent storage.

        Args:
            task_name: Unique identifier for the task.
        """
        pass

    @abstractmethod
    def clear_all_states(self) -> None:
        """Clear all stored task states."""
        pass

    @abstractmethod
    def list_task_states(self) -> list[str]:
        """
        List all task names with saved state.

        Returns:
            List of task names in storage.
        """
        pass

    @abstractmethod
    def load_state(self, workflow: "Workflow") -> None:
        """
        Load all task states from storage into the workflow.

        Restores task status, results, and errors from persistent storage.

        Args:
            workflow: The Workflow instance to populate with stored task states.
        """
        pass

    @abstractmethod
    def save_state(self, workflow: "Workflow") -> None:
        """
        Save all task states from the workflow to persistent storage.

        Persists current task status, results, and errors for resumability.

        Args:
            workflow: The Workflow instance to save from.
        """
        pass


class JSONStateStore(BaseStateStore):
    """
    Lightweight JSON-based state persistence.

    Ideal for:
        - Development and testing
        - Single-machine workflows
        - Small-to-medium task counts (less than 10,000)

    Storage Format:
        {
            "task_name": {
                "status": "COMPLETED",
                "result": {...},
                "error": null,
                "timestamp": "2026-02-22T10:30:45.123456"
            }
        }

    Example:
        store = JSONStateStore("workflow_state.json")
        store.save_task_state("fetch_user", TaskStatus.COMPLETED, result={"id": 42})
        state = store.load_task_state("fetch_user")
    """

    def __init__(self, file_path: str = "workflow_state.json"):
        """
        Initialize JSON state store.

        Args:
            file_path: Path to JSON file for storage.
        """
        self.file_path = Path(file_path)
        self._lock = threading.RLock()

        # Create parent directories if needed
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize empty store if file doesn't exist
        if not self.file_path.exists():
            with self._lock:
                self._write_store({})

    def _read_store(self) -> Dict[str, Any]:
        """Safely read store from disk."""
        try:
            with open(self.file_path, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"State file not found: {self.file_path}", extra={"file_path": str(self.file_path)})
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error in state file: {self.file_path}", extra={"file_path": str(self.file_path), "error": str(e)})
            return {}

    def _write_store(self, store: Dict[str, Any]) -> None:
        """Safely write store to disk with atomic write."""
        # Write to temp file first, then move (atomic on most filesystems)
        temp_path = self.file_path.with_suffix(".tmp")
        with open(temp_path, "w") as f:
            json.dump(store, f, indent=2, default=str)
        temp_path.replace(self.file_path)

    def save_task_state(
        self,
        task_name: str,
        status: TaskStatus,
        result: Any = None,
        error: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Save task state to JSON file."""
        if timestamp is None:
            timestamp = datetime.now()

        with self._lock:
            store = self._read_store()
            store[task_name] = {
                "status": status.name,
                "result": result,
                "error": error,
                "timestamp": timestamp.isoformat(),
            }
            self._write_store(store)

    def load_task_state(self, task_name: str) -> Optional[Dict[str, Any]]:
        """Load task state from JSON file."""
        with self._lock:
            store = self._read_store()
            if task_name not in store:
                return None

            state_data = store[task_name]
            return {
                "status": TaskStatus[state_data["status"]],
                "result": state_data["result"],
                "error": state_data["error"],
                "timestamp": datetime.fromisoformat(state_data["timestamp"]),
            }

    def clear_task_state(self, task_name: str) -> None:
        """Delete task state from JSON file."""
        with self._lock:
            store = self._read_store()
            store.pop(task_name, None)
            self._write_store(store)

    def clear_all_states(self) -> None:
        """Clear all states."""
        with self._lock:
            self._write_store({})

    def list_task_states(self) -> list[str]:
        """List all task names in storage."""
        with self._lock:
            store = self._read_store()
            return list(store.keys())

    def load_state(self, workflow: "Workflow") -> None:
        """Load all task states from storage into the workflow."""
        with self._lock:
            store = self._read_store()
            for task in workflow.get_all_tasks().values():
                if task.name in store:
                    state_data = store[task.name]
                    task.status = TaskStatus[state_data["status"]]
                    task.result = state_data["result"]
                    task.error = state_data["error"]
                    task.completed_at = datetime.fromisoformat(state_data["timestamp"])
                    # Also update workflow result store for context passing
                    if task.status == TaskStatus.COMPLETED:
                        workflow._store_task_result(task.name, task.result)

    def save_state(self, workflow: "Workflow") -> None:
        """Save all task states from the workflow to storage."""
        with self._lock:
            store = self._read_store()
            for task in workflow.get_all_tasks().values():
                store[task.name] = {
                    "status": task.status.name,
                    "result": task.result,
                    "error": task.error,
                    "timestamp": (
                        task.completed_at.isoformat()
                        if task.completed_at
                        else datetime.now().isoformat()
                    ),
                }
            self._write_store(store)


class SQLiteStateStore(BaseStateStore):
    """
    Scalable SQLite-based state persistence.

    Ideal for:
    - Production workflows
    - Long-running applications
    - High concurrency scenarios
    - Querying task history

    Schema:
        CREATE TABLE task_states (
            task_name TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            result TEXT,
            error TEXT,
            timestamp TEXT NOT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )

    Example:
        store = SQLiteStateStore("workflow_state.db")
        store.save_task_state("process_data", TaskStatus.COMPLETED, result=[1,2,3])
        state = store.load_task_state("process_data")
    """

    def __init__(self, db_path: str = "workflow_state.db"):
        """
        Initialize SQLite state store.

        Args:
            db_path: Path to SQLite database file.
        """
        self.db_path = Path(db_path)
        self._lock = threading.RLock()

        # Create parent directories if needed
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize schema
        self._init_db()

    def _init_db(self) -> None:
        """Create database and schema if not exists."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS task_states (
                    task_name TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    result TEXT,
                    error TEXT,
                    timestamp TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with JSON support."""
        # Add small delay for Windows file lock issues
        try:
            conn = sqlite3.connect(self.db_path, timeout=10.0, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.OperationalError:
            time.sleep(0.1)
            conn = sqlite3.connect(self.db_path, timeout=10.0, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            return conn

    def save_task_state(
        self,
        task_name: str,
        status: TaskStatus,
        result: Any = None,
        error: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Save task state to SQLite database."""
        if timestamp is None:
            timestamp = datetime.now()

        # Serialize result to JSON
        result_json = json.dumps(result, default=str) if result is not None else None

        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO task_states
                    (task_name, status, result, error, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (task_name, status.name, result_json, error, timestamp.isoformat()),
                )
                conn.commit()
            finally:
                conn.close()

    def load_task_state(self, task_name: str) -> Optional[Dict[str, Any]]:
        """Load task state from SQLite database."""
        with self._lock:
            conn = self._get_connection()
            try:
                row = conn.execute(
                    "SELECT status, result, error, timestamp FROM task_states WHERE task_name = ?",
                    (task_name,),
                ).fetchone()

                if row is None:
                    return None

                return {
                    "status": TaskStatus[row["status"]],
                    "result": json.loads(row["result"]) if row["result"] else None,
                    "error": row["error"],
                    "timestamp": datetime.fromisoformat(row["timestamp"]),
                }
            finally:
                conn.close()

    def clear_task_state(self, task_name: str) -> None:
        """Delete task state from database."""
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute(
                    "DELETE FROM task_states WHERE task_name = ?", (task_name,)
                )
                conn.commit()
            finally:
                conn.close()
                del conn
                gc.collect()

    def clear_all_states(self) -> None:
        """Clear all states."""
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute("DELETE FROM task_states")
                conn.commit()
            finally:
                conn.close()

    def list_task_states(self) -> list[str]:
        """List all task names in database."""
        with self._lock:
            conn = self._get_connection()
            try:
                rows = conn.execute("SELECT task_name FROM task_states").fetchall()
                return [row["task_name"] for row in rows]
            finally:
                conn.close()
                del conn
                gc.collect()

    def query_task_history(
        self, task_name: str, limit: int = 100
    ) -> list[Dict[str, Any]]:
        """
        Query historical state entries for a task.

        Args:
            task_name: The task name to query.
            limit: Maximum number of records to return.

        Returns:
            List of state records ordered by timestamp (newest first).
        """
        with self._lock:
            conn = self._get_connection()
            try:
                rows = conn.execute(
                    """
                    SELECT status, result, error, timestamp, updated_at
                    FROM task_states
                    WHERE task_name = ?
                    ORDER BY updated_at DESC
                    LIMIT ?
                    """,
                    (task_name, limit),
                ).fetchall()

                return [
                    {
                        "status": TaskStatus[row["status"]],
                        "result": json.loads(row["result"]) if row["result"] else None,
                        "error": row["error"],
                        "timestamp": datetime.fromisoformat(row["timestamp"]),
                        "updated_at": datetime.fromisoformat(row["updated_at"]),
                    }
                    for row in rows
                ]
            finally:
                conn.close()
                del conn
                gc.collect()

    def load_state(self, workflow: "Workflow") -> None:
        """Load all task states from database into the workflow."""
        with self._lock:
            conn = self._get_connection()
            try:
                for task in workflow.get_all_tasks().values():
                    row = conn.execute(
                        "SELECT status, result, error, timestamp FROM task_states WHERE task_name = ?",
                        (task.name,),
                    ).fetchone()

                    if row:
                        task.status = TaskStatus[row["status"]]
                        task.result = (
                            json.loads(row["result"]) if row["result"] else None
                        )
                        task.error = row["error"]
                        task.completed_at = datetime.fromisoformat(row["timestamp"])
                        # Update workflow result store for context passing
                        if task.status == TaskStatus.COMPLETED:
                            workflow._store_task_result(task.name, task.result)
            finally:
                conn.close()

    def save_state(self, workflow: "Workflow") -> None:
        """Save all task states from the workflow to database."""
        with self._lock:
            conn = self._get_connection()
            try:
                for task in workflow.get_all_tasks().values():
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO task_states
                        (task_name, status, result, error, timestamp)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            task.name,
                            task.status.name,
                            json.dumps(task.result) if task.result else None,
                            task.error,
                            (
                                task.completed_at.isoformat()
                                if task.completed_at
                                else datetime.now().isoformat()
                            ),
                        ),
                    )
                conn.commit()
            finally:
                conn.close()
