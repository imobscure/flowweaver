#!/usr/bin/env python3
"""
Use Case 1: ETL (Extract, Transform, Load) Data Pipeline

This example demonstrates a real-world ETL workflow that:
- Extracts data from multiple sources (CSV files)
- Validates data quality
- Transforms and enriches data
- Loads to a "database" (JSON file)
- Logs results for audit trail
"""

import json
import csv
import sys
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from flowweaver import Task, Workflow, SequentialExecutor
from flowweaver.utils import export_mermaid, save_mermaid, view_mermaid


# ==================== ETL Functions ====================


def extract_customers() -> list[dict]:
    """Extract customer data from CSV."""
    print("  └─ Extracting customers...")
    # Simulate reading from CSV
    customers = [
        {"id": "C001", "name": "Alice Johnson", "email": "alice@example.com"},
        {"id": "C002", "name": "Bob Smith", "email": "bob@example.com"},
        {"id": "C003", "name": "Charlie Brown", "email": "charlie@example.com"},
    ]
    return customers


def extract_orders() -> list[dict]:
    """Extract orders data from CSV."""
    print("  └─ Extracting orders...")
    orders = [
        {"id": "O001", "customer_id": "C001", "amount": 150.00, "date": "2024-01-15"},
        {"id": "O002", "customer_id": "C002", "amount": 200.50, "date": "2024-01-16"},
        {"id": "O003", "customer_id": "C001", "amount": 75.25, "date": "2024-01-17"},
    ]
    return orders


def validate_customers(customers: list[dict]) -> list[dict]:
    """Validate customer data - remove invalid records."""
    print("  └─ Validating customers...")
    valid = []
    for customer in customers:
        if customer.get("id") and customer.get("name") and customer.get("email"):
            valid.append(customer)
    print(f"    ✓ {len(valid)}/{len(customers)} customers valid")
    return valid


def validate_orders(orders: list[dict]) -> list[dict]:
    """Validate orders data."""
    print("  └─ Validating orders...")
    valid = []
    for order in orders:
        if order.get("id") and order.get("customer_id") and order.get("amount"):
            valid.append(order)
    print(f"    ✓ {len(valid)}/{len(orders)} orders valid")
    return valid


def enrich_customers(customers: list[dict]) -> list[dict]:
    """Enrich customer data with computed fields."""
    print("  └─ Enriching customers...")
    for c in customers:
        c["created_at"] = datetime.now().isoformat()
        c["status"] = "active"
    return customers


def enrich_orders(orders: list[dict]) -> list[dict]:
    """Enrich order data with computed fields."""
    print("  └─ Enriching orders...")
    for o in orders:
        o["tax"] = o["amount"] * 0.1
        o["total"] = o["amount"] + o["tax"]
        o["processed"] = False
    return orders


def join_customer_orders(customers: list[dict], orders: list[dict]) -> list[dict]:
    """Join customer and order data."""
    print("  └─ Joining customer and order data...")
    customer_map = {c["id"]: c for c in customers}
    result = []
    for order in orders:
        customer = customer_map.get(order["customer_id"])
        if customer:
            result.append(
                {
                    **order,
                    "customer_name": customer["name"],
                    "customer_email": customer["email"],
                }
            )
    print(f"    ✓ Created {len(result)} joined records")
    return result


def load_database(joined_data: list[dict]) -> dict:
    """Load data to "database" (JSON file)."""
    print("  └─ Loading to database...")
    output_file = Path("output_data.json")
    with open(output_file, "w") as f:
        json.dump(
            {
                "timestamp": datetime.now().isoformat(),
                "record_count": len(joined_data),
                "data": joined_data,
            },
            f,
            indent=2,
        )
    print(f"    ✓ Loaded {len(joined_data)} records to {output_file}")
    return {"status": "success", "records_loaded": len(joined_data)}


def generate_audit_log(result: dict) -> None:
    """Generate audit trail."""
    print("  └─ Generating audit log...")
    audit_file = Path("audit_log.txt")
    with open(audit_file, "a") as f:
        f.write(f"\n{datetime.now().isoformat()} - ETL Pipeline Executed\n")
        f.write(f"  Records Loaded: {result['records_loaded']}\n")
        f.write(f"  Status: {result['status']}\n")
    print(f"    ✓ Audit log updated ({audit_file})")


def run_etl_pipeline():
    """Execute the ETL pipeline."""
    print("\n" + "=" * 70)
    print("🔄 ETL PIPELINE EXAMPLE")
    print("=" * 70 + "\n")

    workflow = Workflow(name="ETL Pipeline")

    # Extract phase
    extract_cust = Task(name="extract_customers", fn=extract_customers)
    extract_ord = Task(name="extract_orders", fn=extract_orders)

    # Validate phase (create closures that access workflow results)
    def validate_cust_wrapper():
        customers = workflow.get_task_result("extract_customers")
        return validate_customers(customers)

    def validate_ord_wrapper():
        orders = workflow.get_task_result("extract_orders")
        return validate_orders(orders)

    validate_cust = Task(name="validate_customers", fn=validate_cust_wrapper, retries=1)
    validate_ord = Task(name="validate_orders", fn=validate_ord_wrapper, retries=1)

    # Enrich phase
    def enrich_cust_wrapper():
        customers = workflow.get_task_result("validate_customers")
        return enrich_customers(customers)

    def enrich_ord_wrapper():
        orders = workflow.get_task_result("validate_orders")
        return enrich_orders(orders)

    enrich_cust = Task(name="enrich_customers", fn=enrich_cust_wrapper)
    enrich_ord = Task(name="enrich_orders", fn=enrich_ord_wrapper)

    # Join phase (depends on both)
    def join_wrapper():
        customers = workflow.get_task_result("enrich_customers")
        orders = workflow.get_task_result("enrich_orders")
        return join_customer_orders(customers, orders)

    join_data = Task(name="join_data", fn=join_wrapper)

    # Load phase
    def load_wrapper():
        joined = workflow.get_task_result("join_data")
        return load_database(joined)

    load_data = Task(name="load_database", fn=load_wrapper)

    # Audit phase
    def audit_wrapper():
        result = workflow.get_task_result("load_database")
        return generate_audit_log(result)

    audit_log = Task(name="audit_log", fn=audit_wrapper)

    # Build workflow graph
    workflow.add_task(extract_cust)
    workflow.add_task(extract_ord)

    workflow.add_task(validate_cust, depends_on=["extract_customers"])
    workflow.add_task(validate_ord, depends_on=["extract_orders"])

    workflow.add_task(enrich_cust, depends_on=["validate_customers"])
    workflow.add_task(enrich_ord, depends_on=["validate_orders"])

    workflow.add_task(join_data, depends_on=["enrich_customers", "enrich_orders"])

    workflow.add_task(load_data, depends_on=["join_data"])

    workflow.add_task(audit_log, depends_on=["load_database"])

    # Execute
    print("📊 Execution Plan:")
    plan = workflow.get_execution_plan()
    for idx, layer in enumerate(plan, 1):
        task_names = [t.name for t in layer]
        print(f"  Layer {idx}: {task_names}")

    print("\n🚀 Executing pipeline...\n")
    executor = SequentialExecutor()
    executor.execute(workflow)

    # Print results
    stats = workflow.get_workflow_stats()
    print(f"\n✅ Pipeline Complete!")
    print(f"  Total Tasks: {stats['total_tasks']}")
    print(f"  Completed: {stats['completed']}")
    print(f"  Failed: {stats['failed']}")
    print(f"  Execution Time: {stats['total_time_seconds']:.3f}s")

    # Show final result
    final_result = workflow.get_task_result("load_database")
    print(f"\n📈 Result: {final_result}")

    # --- Mermaid Visualization ---
    print("\n📊 Mermaid Diagram (post-execution):")
    print(export_mermaid(workflow, orientation="TD"))
    save_mermaid(workflow, "etl_pipeline_diagram.md")
    view_mermaid(workflow, orientation="TD")


if __name__ == "__main__":
    run_etl_pipeline()
    print("\n" + "=" * 70 + "\n")
