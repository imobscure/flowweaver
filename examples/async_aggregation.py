#!/usr/bin/env python3
"""
Use Case 3: Async Data Aggregation

Demonstrates real-time async workflow for:
- Fetching data from multiple sources concurrently
- Aggregating results
- Computing analytics
- Real-time monitoring with callbacks
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from flowweaver import Task, Workflow, AsyncExecutor, TaskStatus


# ==================== Async Data Functions ====================


async def fetch_user_data(user_id: int) -> dict:
    """Simulate fetching user data from API."""
    await asyncio.sleep(0.2)  # Simulate network latency
    return {
        "id": user_id,
        "name": f"User#{user_id}",
        "email": f"user{user_id}@example.com",
        "profile_views": 100 + user_id * 10,
    }


async def fetch_user_activity(user_id: int) -> dict:
    """Simulate fetching user activity from API."""
    await asyncio.sleep(0.15)  # Different latency
    return {
        "user_id": user_id,
        "posts": 5 + user_id,
        "followers": 100 * user_id,
        "engagement_rate": 0.75 + (user_id * 0.01),
    }


async def fetch_user_analytics(user_id: int) -> dict:
    """Simulate fetching user analytics."""
    await asyncio.sleep(0.1)
    return {
        "user_id": user_id,
        "page_visits": 500 + user_id * 50,
        "session_duration": 5 + user_id,
        "bounce_rate": 0.20 - (user_id * 0.01),
    }


async def aggregate_data(tasks_dict: dict) -> dict:
    """Aggregate all user data together."""
    print("  └─ Aggregating data from all sources...")

    aggregated = {}
    for key, value in tasks_dict.items():
        if isinstance(value, dict):
            aggregated.update(value)

    return aggregated


async def compute_analytics(aggregated: dict) -> dict:
    """Compute advanced analytics on aggregated data."""
    print("  └─ Computing analytics...")
    await asyncio.sleep(0.05)

    return {
        "total_users": 5,
        "avg_followers": aggregated.get("followers", 0) / 5 if aggregated else 0,
        "avg_engagement": aggregated.get("engagement_rate", 0) / 5 if aggregated else 0,
        "total_posts": aggregated.get("posts", 0),
        "compute_time": "0.05s",
    }


async def generate_async_report(analytics: dict) -> dict:
    """Generate async report."""
    print("  └─ Generating report...")
    await asyncio.sleep(0.05)

    return {
        "timestamp": datetime.now().isoformat(),
        "summary": analytics,
        "status": "complete",
    }


def on_task_status_change(task_name: str, status: TaskStatus) -> None:
    """Real-time callback for task status changes."""
    status_icon = {
        TaskStatus.PENDING: "⏳",
        TaskStatus.RUNNING: "🔄",
        TaskStatus.COMPLETED: "✅",
        TaskStatus.FAILED: "❌",
    }
    icon = status_icon.get(status, "")
    print(f"    {icon} {task_name}: {status.value}")


def on_task_retry(task_name: str, attempt: int) -> None:
    """Real-time callback for retry attempts."""
    print(f"    🔁 {task_name}: retry attempt #{attempt}")


async def run_async_pipeline():
    """Execute the async data aggregation pipeline."""
    print("\n" + "=" * 70)
    print("⚡ ASYNC DATA AGGREGATION PIPELINE EXAMPLE")
    print("=" * 70 + "\n")

    workflow = Workflow(name="Async Data Aggregation")

    # Create parallel user data fetch tasks
    print("📊 Building workflow with 5 concurrent users...\n")

    user_ids = [1, 2, 3, 4, 5]
    user_data_tasks = {}
    user_activity_tasks = {}
    user_analytics_tasks = {}

    for user_id in user_ids:
        # Create async closures to capture user_id
        async def fetch_user(uid: int = user_id) -> dict:
            return await fetch_user_data(uid)

        async def fetch_activity(uid: int = user_id) -> dict:
            return await fetch_user_activity(uid)

        async def fetch_analytics(uid: int = user_id) -> dict:
            return await fetch_user_analytics(uid)

        # Create tasks with callbacks
        user_data_task = Task(
            name=f"user_data_{user_id}",
            fn=fetch_user,
            on_status_change=on_task_status_change,
            on_retry=on_task_retry,
        )
        user_activity_task = Task(
            name=f"user_activity_{user_id}",
            fn=fetch_activity,
            on_status_change=on_task_status_change,
        )
        user_analytics_task = Task(
            name=f"user_analytics_{user_id}",
            fn=fetch_analytics,
            on_status_change=on_task_status_change,
        )

        workflow.add_task(user_data_task)
        workflow.add_task(user_activity_task)
        workflow.add_task(user_analytics_task)

        user_data_tasks[f"user_data_{user_id}"] = user_data_task
        user_activity_tasks[f"user_activity_{user_id}"] = user_activity_task
        user_analytics_tasks[f"user_analytics_{user_id}"] = user_analytics_task

    # Aggregation task depends on all user data
    all_user_tasks = [f"user_data_{i}" for i in user_ids]
    all_user_tasks += [f"user_activity_{i}" for i in user_ids]
    all_user_tasks += [f"user_analytics_{i}" for i in user_ids]

    async def aggregate_wrapper() -> dict:
        # Collect results from all tasks
        results = {}
        for task_name, task in workflow.get_all_tasks().items():
            if task_name in all_user_tasks:
                results[task_name] = task.result
        return await aggregate_data(results)

    aggregate_task = Task(
        name="aggregate",
        fn=aggregate_wrapper,
        on_status_change=on_task_status_change,
    )
    workflow.add_task(aggregate_task, depends_on=all_user_tasks)

    # Analytics task
    async def analytics_wrapper() -> dict:
        agg_result = workflow.get_task_result("aggregate")
        return await compute_analytics(agg_result or {})

    analytics_task = Task(
        name="compute_analytics",
        fn=analytics_wrapper,
        on_status_change=on_task_status_change,
    )
    workflow.add_task(analytics_task, depends_on=["aggregate"])

    # Report task
    async def report_wrapper() -> dict:
        analytics_result = workflow.get_task_result("compute_analytics")
        return await generate_async_report(analytics_result or {})

    report_task = Task(
        name="generate_report",
        fn=report_wrapper,
        on_status_change=on_task_status_change,
    )
    workflow.add_task(report_task, depends_on=["compute_analytics"])

    # Show execution plan
    print("📋 Execution Plan:")
    plan = workflow.get_execution_plan()
    for idx, layer in enumerate(plan, 1):
        task_names = [t.name for t in layer]
        print(
            f"  Layer {idx} ({len(layer)} parallel): {task_names[:3]}{'...' if len(task_names) > 3 else ''}"
        )

    print("\n⚙️  Executing async pipeline...\n")

    # Execute with AsyncExecutor for true concurrency
    executor = AsyncExecutor()
    executor.execute(workflow)

    # Print results
    stats = workflow.get_workflow_stats()
    print(f"\n✅ Async Pipeline Complete!")
    print(f"  Total Tasks: {stats['total_tasks']}")
    print(f"  Completed: {stats['completed']}")
    print(f"  Execution Time: {stats['total_time_seconds']:.3f}s")
    print(f"\n💡 Note: Fetching 5 users * 3 sources = 15 tasks in parallel")
    print(
        f"   Sequential would take ~0.9s, async completed in ~{stats['total_time_seconds']:.3f}s"
    )

    # Show analytics
    analytics = workflow.get_task_result("compute_analytics")
    if analytics:
        print(f"\n📊 Analytics:")
        for key, value in analytics.items():
            if isinstance(value, float):
                print(f"  {key}: {value:.2f}")
            else:
                print(f"  {key}: {value}")


if __name__ == "__main__":
    # Note: We can't call asyncio.run() here because AsyncExecutor creates its own event loop
    # Instead, we'll just call the function directly and let it manage the workflow

    import asyncio

    # Get the workflow setup
    workflow = Workflow(name="Async Data Aggregation")

    # Create parallel user data fetch tasks
    print("\n" + "=" * 70)
    print("⚡ ASYNC DATA AGGREGATION PIPELINE EXAMPLE")
    print("=" * 70 + "\n")
    print("📊 Building workflow with 5 concurrent users...\n")

    user_ids = [1, 2, 3, 4, 5]
    user_data_tasks = {}
    user_activity_tasks = {}
    user_analytics_tasks = {}

    for user_id in user_ids:
        # Create async closures to capture user_id
        async def fetch_user(uid: int = user_id) -> dict:
            return await fetch_user_data(uid)

        async def fetch_activity(uid: int = user_id) -> dict:
            return await fetch_user_activity(uid)

        async def fetch_analytics(uid: int = user_id) -> dict:
            return await fetch_user_analytics(uid)

        # Create tasks with callbacks
        user_data_task = Task(
            name=f"user_data_{user_id}",
            fn=fetch_user,
            on_status_change=on_task_status_change,
            on_retry=on_task_retry,
        )
        user_activity_task = Task(
            name=f"user_activity_{user_id}",
            fn=fetch_activity,
            on_status_change=on_task_status_change,
        )
        user_analytics_task = Task(
            name=f"user_analytics_{user_id}",
            fn=fetch_analytics,
            on_status_change=on_task_status_change,
        )

        workflow.add_task(user_data_task)
        workflow.add_task(user_activity_task)
        workflow.add_task(user_analytics_task)

        user_data_tasks[f"user_data_{user_id}"] = user_data_task
        user_activity_tasks[f"user_activity_{user_id}"] = user_activity_task
        user_analytics_tasks[f"user_analytics_{user_id}"] = user_analytics_task

    # Aggregation task depends on all user data
    all_user_tasks = [f"user_data_{i}" for i in user_ids]
    all_user_tasks += [f"user_activity_{i}" for i in user_ids]
    all_user_tasks += [f"user_analytics_{i}" for i in user_ids]

    async def aggregate_wrapper() -> dict:
        # Collect results from all tasks
        results = {}
        for task_name, task in workflow.get_all_tasks().items():
            if task_name in all_user_tasks:
                results[task_name] = task.result
        return await aggregate_data(results)

    aggregate_task = Task(
        name="aggregate",
        fn=aggregate_wrapper,
        on_status_change=on_task_status_change,
    )
    workflow.add_task(aggregate_task, depends_on=all_user_tasks)

    # Analytics task
    async def analytics_wrapper() -> dict:
        agg_result = workflow.get_task_result("aggregate")
        return await compute_analytics(agg_result or {})

    analytics_task = Task(
        name="compute_analytics",
        fn=analytics_wrapper,
        on_status_change=on_task_status_change,
    )
    workflow.add_task(analytics_task, depends_on=["aggregate"])

    # Report task
    async def report_wrapper() -> dict:
        analytics_result = workflow.get_task_result("compute_analytics")
        return await generate_async_report(analytics_result or {})

    report_task = Task(
        name="generate_report",
        fn=report_wrapper,
        on_status_change=on_task_status_change,
    )
    workflow.add_task(report_task, depends_on=["compute_analytics"])

    # Show execution plan
    print("📋 Execution Plan:")
    plan = workflow.get_execution_plan()
    for idx, layer in enumerate(plan, 1):
        task_names = [t.name for t in layer]
        print(
            f"  Layer {idx} ({len(layer)} parallel): {task_names[:3]}{'...' if len(task_names) > 3 else ''}"
        )

    print("\n⚙️  Executing async pipeline...\n")

    # Execute with AsyncExecutor for true concurrency
    executor = AsyncExecutor()
    executor.execute(workflow)

    # Print results
    stats = workflow.get_workflow_stats()
    print(f"\n✅ Async Pipeline Complete!")
    print(f"  Total Tasks: {stats['total_tasks']}")
    print(f"  Completed: {stats['completed']}")
    print(f"  Execution Time: {stats['total_time_seconds']:.3f}s")
    print(f"\n💡 Note: Fetching 5 users * 3 sources = 15 tasks in parallel")
    print(
        f"   Sequential would take ~0.9s, async completed in ~{stats['total_time_seconds']:.3f}s"
    )

    # Show analytics
    analytics = workflow.get_task_result("compute_analytics")
    if analytics:
        print(f"\n📊 Analytics:")
        for key, value in analytics.items():
            if isinstance(value, float):
                print(f"  {key}: {value:.2f}")
            else:
                print(f"  {key}: {value}")

    print("\n" + "=" * 70 + "\n")
