# FlowWeaver v0.3.2 - Operating Guide

## Table of Contents

1. [Starting & Stopping Workflows](#starting--stopping-workflows)
2. [Monitoring Workflows](#monitoring-workflows)
3. [Troubleshooting Common Issues](#troubleshooting-common-issues)
4. [Performance Tuning](#performance-tuning)
5. [Disaster Recovery](#disaster-recovery)
6. [Upgrading FlowWeaver](#upgrading-flowweaver)
7. [Operational Runbooks](#operational-runbooks)

---

## Starting & Stopping Workflows

### Basic Workflow Execution

```python
#!/usr/bin/env python3
"""
Production workflow starter script
Place in: /opt/flowweaver/bin/run_workflow.py
"""

import sys
import logging
import signal
from pathlib import Path
from datetime import datetime

from flowweaver import (
    Workflow,
    Task,
    ThreadedExecutor,
    SQLiteStateStore,
    TaskStatus
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/flowweaver/production.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger('flowweaver.operator')

class WorkflowRunner:
    def __init__(self, workflow_name: str, state_dir: str = "/var/lib/flowweaver"):
        self.workflow_name = workflow_name
        self.state_dir = Path(state_dir)
        self.state_store = SQLiteStateStore(str(self.state_dir / f"{workflow_name}.db"))
        self.executor = ThreadedExecutor(max_workers=4, state_store=self.state_store)
        self.workflow = None
        self._running = True
    
    def setup_signal_handlers(self):
        """Handle graceful shutdown"""
        def sigterm_handler(signum, frame):
            logger.info(f"Received SIGTERM ({signum}), initiating graceful shutdown...")
            self._running = False
        
        signal.signal(signal.SIGTERM, sigterm_handler)
        signal.signal(signal.SIGINT, sigterm_handler)
    
    def build_workflow(self):
        """Override in subclass to define workflow"""
        raise NotImplementedError("Subclass must implement build_workflow()")
    
    def run(self):
        """Execute workflow with error handling"""
        try:
            logger.info(f"Starting workflow: {self.workflow_name}")
            logger.info(f"State store: {self.state_store.store_path}")
            
            start_time = datetime.now()
            
            # Build workflow
            self.build_workflow()
            
            if not self.workflow:
                raise ValueError("Workflow not built")
            
            # Execute
            self.executor.execute(self.workflow)
            
            # Report results
            duration = (datetime.now() - start_time).total_seconds()
            
            completed_count = sum(
                1 for t in self.workflow.tasks 
                if t.status == TaskStatus.COMPLETED
            )
            failed_count = sum(
                1 for t in self.workflow.tasks 
                if t.status == TaskStatus.FAILED
            )
            
            logger.info(f"Workflow completed in {duration:.2f}s")
            logger.info(f"Tasks: {completed_count} completed, {failed_count} failed")
            
            if failed_count > 0:
                logger.error("Workflow had failures - check logs")
                return 1
            
            logger.info("Workflow executed successfully")
            return 0
        
        except KeyboardInterrupt:
            logger.warning("Workflow interrupted by user")
            return 130
        
        except Exception as e:
            logger.error(f"Workflow failed: {e}", exc_info=True)
            return 1

# Example: Customer Data Pipeline
class CustomerDataPipeline(WorkflowRunner):
    def build_workflow(self):
        from flowweaver import task
        
        self.workflow = Workflow(
            name="customer_data_etl",
            description="Daily customer data extraction and loading"
        )
        
        @task()
        def extract_customers():
            logger.info("Extracting customer data from CRM...")
            # Your extraction logic here
            return {"count": 1000, "data": []}
        
        @task()
        def validate_data(extract_customers=None):
            logger.info(f"Validating {extract_customers['count']} records...")
            # Your validation logic here
            return extract_customers["count"]
        
        @task()
        def load_warehouse(validate_data=None):
            logger.info(f"Loading {validate_data} records to warehouse...")
            # Your load logic here
            return {"loaded": validate_data}
        
        self.workflow.add_task(extract_customers)
        self.workflow.add_task(validate_data, depends_on=["extract_customers"])
        self.workflow.add_task(load_warehouse, depends_on=["validate_data"])

if __name__ == "__main__":
    # Run specific workflow
    if len(sys.argv) > 1:
        workflow_name = sys.argv[1]
    else:
        workflow_name = "customer_data_etl"
    
    if workflow_name == "customer_data_etl":
        runner = CustomerDataPipeline(workflow_name)
    else:
        logger.error(f"Unknown workflow: {workflow_name}")
        sys.exit(1)
    
    runner.setup_signal_handlers()
    exit_code = runner.run()
    sys.exit(exit_code)
```

### Running via Cron

```bash
# File: /etc/cron.d/flowweaver
# Run customer pipeline daily at 2 AM

0 2 * * * flowweaver cd /opt/flowweaver && python -u bin/run_workflow.py customer_data_etl >> /var/log/flowweaver/cron.log 2>&1
```

### Running via Systemd

```ini
# File: /etc/systemd/system/flowweaver-pipeline.service

[Unit]
Description=FlowWeaver Customer Data Pipeline
After=network.target

[Service]
Type=oneshot
User=flowweaver
WorkingDirectory=/opt/flowweaver
ExecStart=/usr/bin/python3 bin/run_workflow.py customer_data_etl
StandardOutput=journal
StandardError=journal
SyslogIdentifier=flowweaver

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and run
sudo systemctl enable flowweaver-pipeline
sudo systemctl start flowweaver-pipeline

# Check status
sudo systemctl status flowweaver-pipeline

# View logs
sudo journalctl -u flowweaver-pipeline -f
```

---

## Monitoring Workflows

### Health Check Endpoint

```python
#!/usr/bin/env python3
"""Health check for monitoring systems"""

import flask
import json
from datetime import datetime
from pathlib import Path

app = flask.Flask(__name__)

@app.route('/health', methods=['GET'])
def health():
    """
    Returns health status
    Use with: curl http://localhost:5000/health
    """
    try:
        # Check state store accessibility
        from flowweaver import SQLiteStateStore
        
        store = SQLiteStateStore("/var/lib/flowweaver/state.db")
        
        # Check database
        import sqlite3
        conn = sqlite3.connect(store.store_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM tasks")
        task_count = cursor.fetchone()[0]
        conn.close()
        
        return flask.jsonify({
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "checks": {
                "state_store": "ok",
                "saved_tasks": task_count,
                "version": "0.3.2"
            }
        }), 200
    
    except Exception as e:
        return flask.jsonify({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 503

@app.route('/metrics', methods=['GET'])
def metrics():
    """Prometheus format metrics"""
    try:
        from flowweaver import SQLiteStateStore, TaskStatus
        import sqlite3
        
        store = SQLiteStateStore("/var/lib/flowweaver/state.db")
        conn = sqlite3.connect(store.store_path)
        cursor = conn.cursor()
        
        # Count tasks by status
        cursor.execute("SELECT status, COUNT(*) FROM tasks GROUP BY status")
        
        metrics = "# HELP flowweaver_tasks_total Total tasks by status\n"
        metrics += "# TYPE flowweaver_tasks_total gauge\n"
        
        for status, count in cursor.fetchall():
            metrics += f'flowweaver_tasks_total{{status="{status}"}} {count}\n'
        
        conn.close()
        
        return metrics, 200, {'Content-Type': 'text/plain'}
    
    except Exception as e:
        return f"Error: {e}", 503

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
```

### Checking Task Status

```bash
# List all completed tasks
sqlite3 /var/lib/flowweaver/state.db \
  "SELECT task_name, timestamp FROM tasks WHERE status = 'COMPLETED' ORDER BY timestamp DESC LIMIT 10;"

# Check failed tasks
sqlite3 /var/lib/flowweaver/state.db \
  "SELECT task_name, timestamp FROM tasks WHERE status = 'FAILED';"

# Get task count by status
sqlite3 /var/lib/flowweaver/state.db \
  "SELECT status, COUNT(*) FROM tasks GROUP BY status;"

# Export task history
sqlite3 /var/lib/flowweaver/state.db -header -csv \
  "SELECT * FROM tasks;" > task_history.csv
```

### Monitoring via Logs

```bash
# Watch live logs
tail -f /var/log/flowweaver/production.log

# Count errors in last hour
grep "ERROR" /var/log/flowweaver/production.log | \
  awk -F: '$1 > (now-3600) {count++} END {print count}' now=$(date +%s)

# Track task duration
grep "task.*duration" /var/log/flowweaver/production.log | \
  awk '{print $NF}' | sort -n | \
  awk '{sum+=$1; n++} END {print "Avg:", sum/n, "Max:", $NF}'
```

---

## Troubleshooting Common Issues

### Issue: Workflow Hanging

**Symptoms:**
- Process doesn't respond
- State store shows task in RUNNING state
- CPU usage inconsistent

**Diagnosis:**
```bash
# Check process status
ps aux | grep run_workflow.py

# Check task state
sqlite3 /var/lib/flowweaver/state.db \
  "SELECT task_name, status FROM tasks WHERE status = 'RUNNING';"

# Check system resources
top -b -n 1 | head -20  # CPU/memory
df -h                    # Disk space
lsof -p <PID>           # Open files
```

**Common Causes & Solutions:**

1. **Task waiting on I/O**
   - Solution: Increase timeout if legitimate
   - Solution: Add retries for transient failures

2. **Deadlock on state store lock**
   - Solution: Restart workflow
   - Solution: Check file permissions on state store

3. **Memory exhaustion**
   - Solution: Use state store to offload results to disk
   - Solution: Reduce max_workers in ThreadedExecutor

```python
# FIX: Use state store to prevent memory issues
state_store = SQLiteStateStore("/var/lib/flowweaver/state.db")
executor = ThreadedExecutor(max_workers=4, state_store=state_store)
```

### Issue: High CPU Usage

**Diagnosis:**
```bash
# Check CPU usage per thread
top -H -p <PID>

# Profile with py-spy
pip install py-spy
sudo py-spy record -o profile.svg -p <PID> -- sleep 10
```

**Solutions:**

1. **Too many worker threads**
   ```python
   # BEFORE: Over-subscribed threads
   executor = ThreadedExecutor(max_workers=64)
   
   # AFTER: Tuned to system
   # For I/O-bound: cores * 2-4
   # For CPU-bound: cores only
   import os
   cores = os.cpu_count()
   executor = ThreadedExecutor(max_workers=cores * 2)
   ```

2. **Task doing busy-wait**
   ```python
   # BEFORE: Busy loop
   @task()
   def wait_for_event():
       while not event.is_set():
           pass  # Wastes CPU
   
   # AFTER: Efficient wait
   @task()
   def wait_for_event():
       event.wait(timeout=60)  # Blocks efficiently
   ```

### Issue: State Store Locked/Corrupted

**Symptoms:**
- "database is locked" errors
- Corrupted JSON file
- Missing tasks in state

**Solutions:**

```bash
# SQLite: Check integrity
sqlite3 /var/lib/flowweaver/state.db "PRAGMA integrity_check;"

# SQLite: Rebuild if corrupted
sqlite3 /var/lib/flowweaver/state.db "VACUUM;"

# JSON: Format check
python3 -m json.tool /var/lib/flowweaver/state.json > /dev/null && \
  echo "Valid JSON" || echo "Invalid JSON"

# Clear corrupted state (WARNING: Loses history)
# Backup first!
cp /var/lib/flowweaver/state.db /var/lib/flowweaver/state.db.backup

# For SQLite:
rm /var/lib/flowweaver/state.db
# Workflow will start fresh

# For JSON:
rm /var/lib/flowweaver/state.json
# Workflow will start fresh
```

---

## Performance Tuning

### Thread Pool Sizing

```python
import os
import time
from flowweaver import ThreadedExecutor

# Determine optimal worker count
cores = os.cpu_count()

# I/O-bound (network, database, file I/O)
io_workers = cores * 3  # Experiment: 2-4x cores

# CPU-bound (calculations, processing)
cpu_workers = cores  # 1-2x cores for hyperthreading

# Profile different sizes
for max_workers in [cores, cores * 2, cores * 3]:
    executor = ThreadedExecutor(max_workers=max_workers)
    
    start = time.time()
    executor.execute(workflow)
    duration = time.time() - start
    
    print(f"Workers={max_workers}: {duration:.2f}s")
```

### State Store Performance

```bash
# Monitor state store latency
strace -c python3 run_workflow.py 2>&1 | grep "sqlite3\|open\|write"

# Compare JSONStateStore vs SQLiteStateStore
# SQLite is faster for large datasets (indexed queries)
# JSON is simpler for small datasets (<100 tasks)
```

### Task Batching

```python
# BEFORE: 1000 individual tasks (slow)
for user_id in range(1000):
    workflow.add_task(Task(f"user_{user_id}", process_user))

# AFTER: 10 batches of 100 users (fast)
for batch_num in range(10):
    user_ids = range(batch_num * 100, (batch_num + 1) * 100)
    workflow.add_task(
        Task(f"batch_{batch_num}", process_batch, user_ids)
    )
```

---

## Disaster Recovery

### Backup State Store

```bash
#!/bin/bash
# File: /usr/local/bin/backup_flowweaver.sh
# Run daily: 0 3 * * * /usr/local/bin/backup_flowweaver.sh

BACKUP_DIR="/var/backups/flowweaver"
STATE_DB="/var/lib/flowweaver/state.db"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup database
cp $STATE_DB $BACKUP_DIR/state.db.$DATE

# Keep only 30 days of backups
find $BACKUP_DIR -name "state.db.*" -mtime +30 -delete

echo "FlowWeaver backup completed: $DATE"
```

### Restore from Backup

```bash
# Stop workflows
sudo systemctl stop flowweaver-pipeline

# Restore from backup
cp /var/backups/flowweaver/state.db.20240115_030000 \
   /var/lib/flowweaver/state.db

# Verify
sqlite3 /var/lib/flowweaver/state.db "SELECT COUNT(*) FROM tasks;"

# Restart
sudo systemctl start flowweaver-pipeline
```

### Recovery Procedure if State Lost

```python
"""Recovery script if state store is lost"""

from flowweaver import (
    Workflow, Task, SequentialExecutor, SQLiteStateStore, TaskStatus
)
import logging

logger = logging.getLogger(__name__)

def recovery_workflow():
    """Rebuild workflow state from external sources"""
    
    workflow = Workflow("recovery")
    
    @task()
    def check_previous_runs():
        """Check if previous runs completed in external system"""
        # Query your actual data system
        # Return which tasks actually completed
        return {
            "completed": ["fetch", "validate"],
            "pending": ["transform", "load"]
        }
    
    @task()
    def rebuild_state(check_previous_runs=None):
        """Reconstruct state store from known completion"""
        store = SQLiteStateStore("/var/lib/flowweaver/state.db")
        
        for task_name in check_previous_runs["completed"]:
            store.save_task_state(
                task_name,
                TaskStatus.COMPLETED,
                {"recovered": True},
                None,
                datetime.now()
            )
        
        logger.info(f"Recovered {len(check_previous_runs['completed'])} tasks")
    
    workflow.add_task(check_previous_runs)
    workflow.add_task(rebuild_state, depends_on=["check_previous_runs"])
    
    executor = SequentialExecutor()
    executor.execute(workflow)
```

---

## Upgrading FlowWeaver

### Check Current Version

```python
from flowweaver import __version__
print(f"FlowWeaver version: {__version__}")
```

### Upgrade Process

```bash
# 1. Backup state store
cp /var/lib/flowweaver/state.db /var/lib/flowweaver/state.db.backup

# 2. Stop running workflows
sudo systemctl stop flowweaver-pipeline

# 3. Upgrade package
pip install --upgrade flowweaver

# 4. Verify installation
python3 -c "from flowweaver import Workflow; print('✓ OK')"

# 5. Run test workflow
python3 test_sde2_complete.py

# 6. Restart workflows
sudo systemctl start flowweaver-pipeline

# 7. Verify logs
tail -f /var/log/flowweaver/production.log
```

### Backward Compatibility

- v0.3.x is fully backward compatible
- Existing state stores work without migration
- No breaking changes to API

---

## Operational Runbooks

### Runbook: Handle Failed Task

```markdown
# When a task fails

## 1. Identify the failure
- Check logs: grep ERROR /var/log/flowweaver/production.log
- Check state: sqlite3 ... "SELECT * FROM tasks WHERE status='FAILED';"

## 2. Determine root cause
- Network error? (retry should help)
- Data error? (fix data, clear state, retry)
- Code error? (fix code, redeploy)

## 3. Fix the issue
- If transient: Increase retries in task definition
- If data: Fix data source, then:
  - Clear that task's state: sqlite3 ... "DELETE FROM tasks WHERE task_name=..."
  - Re-run workflow (will retry from that point)
- If code: Deploy fix, clear state, re-run

## 4. Verify
- Run health check: curl http://localhost:5000/health
- Check logs: tail -f /var/log/flowweaver/production.log
```

### Runbook: Restart Failed Workflow

```python
"""
Run this script to restart a workflow that failed
Handles resuming from last successful task
"""

from flowweaver import SQLiteStateStore, TaskStatus
import sqlite3

def restart_workflow(workflow_name: str):
    # Connect to state store
    store = SQLiteStateStore(f"/var/lib/flowweaver/{workflow_name}.db")
    
    # Find last failed task
    conn = sqlite3.connect(store.store_path)
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT task_name FROM tasks WHERE status=? ORDER BY timestamp DESC LIMIT 1",
        (TaskStatus.FAILED.value,)
    )
    
    failed_task = cursor.fetchone()
    
    if failed_task:
        task_name = failed_task[0]
        print(f"Last failed task: {task_name}")
        
        # Clear the failed task state to allow retry
        cursor.execute("DELETE FROM tasks WHERE task_name = ?", (task_name,))
        conn.commit()
        
        print(f"Cleared state for {task_name}")
        print("Re-run workflow - will resume from this task")
    else:
        print("No failed tasks found")
    
    conn.close()

if __name__ == "__main__":
    restart_workflow("customer_data_etl")
```

---

**Version**: 0.3.2 - Production Ready
**Last Updated**: February 2026
