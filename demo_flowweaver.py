#!/usr/bin/env python3
"""
FlowWeaver Local Demo — Large Visual DAG

Install first:  pip install flowweaver
Then run:       python demo_flowweaver.py

This builds a realistic, large multi-stage data platform workflow with
30+ tasks across 7 layers, executes it, and opens the colorful DAG
in your browser automatically.
"""

import time
from flowweaver import Task, Workflow, SequentialExecutor, TaskStatus
from flowweaver.utils import export_mermaid, save_mermaid, view_mermaid


# =============================================================================
#  Layer 1 — Data Ingestion (4 parallel sources)
# =============================================================================

def ingest_api_users():
    time.sleep(0.05)
    return {"source": "api", "rows": 12000}

def ingest_csv_orders():
    time.sleep(0.05)
    return {"source": "csv", "rows": 45000}

def ingest_db_products():
    time.sleep(0.05)
    return {"source": "db", "rows": 8500}

def ingest_s3_clickstream():
    time.sleep(0.05)
    return {"source": "s3", "rows": 200000}


# =============================================================================
#  Layer 2 — Validation (one per source)
# =============================================================================

def validate_users():    return {"valid": 11800, "invalid": 200}
def validate_orders():   return {"valid": 44500, "invalid": 500}
def validate_products(): return {"valid": 8500,  "invalid": 0}
def validate_clicks():   return {"valid": 198000, "invalid": 2000}


# =============================================================================
#  Layer 3 — Enrichment & Transformation
# =============================================================================

def enrich_users():       return {"enriched": 11800, "geo_tagged": True}
def enrich_orders():      return {"enriched": 44500, "currency_normalized": True}
def normalize_products(): return {"normalized": 8500, "categories_mapped": True}
def sessionize_clicks():  return {"sessions": 32000, "avg_duration": "4m12s"}


# =============================================================================
#  Layer 4 — Feature Engineering & Joins
# =============================================================================

def join_user_orders():   return {"joined_rows": 44500}
def join_product_catalog(): return {"catalog_rows": 8500}
def build_user_features():  return {"features": 42, "users": 11800}
def build_click_features(): return {"features": 18, "sessions": 32000}
def aggregate_revenue():    return {"total_revenue": 1_250_000, "currency": "USD"}


# =============================================================================
#  Layer 5 — ML & Analytics
# =============================================================================

def train_churn_model():      return {"model": "xgboost", "auc": 0.91}
def train_recommender():      return {"model": "als", "ndcg": 0.78}
def compute_rfm_segments():   return {"segments": 5, "customers": 11800}
def compute_funnel_metrics(): return {"conversion_rate": 0.034}


# =============================================================================
#  Layer 6 — Output Generation
# =============================================================================

def generate_executive_report():   return {"pages": 12, "format": "pdf"}
def generate_marketing_segments(): return {"segments_exported": 5}
def export_predictions_to_db():    return {"predictions_written": 11800}
def publish_dashboard_data():      return {"dashboards_refreshed": 4}
def send_slack_alerts():           return {"alerts_sent": 3}


# =============================================================================
#  Layer 7 — Final Orchestration
# =============================================================================

def run_data_quality_audit(): return {"checks_passed": 47, "checks_failed": 0}
def archive_raw_data():       return {"archived_gb": 2.4}
def log_pipeline_metadata():  return {"pipeline_id": "run_20260228_001", "status": "success"}


# =============================================================================
#  Build the Workflow
# =============================================================================

def build_big_workflow() -> Workflow:
    wf = Workflow(name="DataPlatform Pipeline v2")

    # --- Layer 1: Ingestion ---
    wf.add_task(Task(name="Ingest API Users",      fn=ingest_api_users))
    wf.add_task(Task(name="Ingest CSV Orders",      fn=ingest_csv_orders))
    wf.add_task(Task(name="Ingest DB Products",     fn=ingest_db_products))
    wf.add_task(Task(name="Ingest S3 Clickstream",  fn=ingest_s3_clickstream))

    # --- Layer 2: Validation ---
    wf.add_task(Task(name="Validate Users",    fn=validate_users),    depends_on=["Ingest API Users"])
    wf.add_task(Task(name="Validate Orders",   fn=validate_orders),   depends_on=["Ingest CSV Orders"])
    wf.add_task(Task(name="Validate Products", fn=validate_products), depends_on=["Ingest DB Products"])
    wf.add_task(Task(name="Validate Clicks",   fn=validate_clicks),   depends_on=["Ingest S3 Clickstream"])

    # --- Layer 3: Enrichment ---
    wf.add_task(Task(name="Enrich Users",        fn=enrich_users),       depends_on=["Validate Users"])
    wf.add_task(Task(name="Enrich Orders",       fn=enrich_orders),      depends_on=["Validate Orders"])
    wf.add_task(Task(name="Normalize Products",  fn=normalize_products), depends_on=["Validate Products"])
    wf.add_task(Task(name="Sessionize Clicks",   fn=sessionize_clicks),  depends_on=["Validate Clicks"])

    # --- Layer 4: Feature Engineering & Joins ---
    wf.add_task(Task(name="Join User-Orders",     fn=join_user_orders),     depends_on=["Enrich Users", "Enrich Orders"])
    wf.add_task(Task(name="Join Product Catalog", fn=join_product_catalog), depends_on=["Normalize Products", "Enrich Orders"])
    wf.add_task(Task(name="Build User Features",  fn=build_user_features),  depends_on=["Enrich Users", "Sessionize Clicks"])
    wf.add_task(Task(name="Build Click Features", fn=build_click_features), depends_on=["Sessionize Clicks"])
    wf.add_task(Task(name="Aggregate Revenue",    fn=aggregate_revenue),    depends_on=["Join User-Orders", "Join Product Catalog"])

    # --- Layer 5: ML & Analytics ---
    wf.add_task(Task(name="Train Churn Model",      fn=train_churn_model),      depends_on=["Build User Features", "Join User-Orders"])
    wf.add_task(Task(name="Train Recommender",       fn=train_recommender),      depends_on=["Build User Features", "Build Click Features"])
    wf.add_task(Task(name="Compute RFM Segments",    fn=compute_rfm_segments),   depends_on=["Join User-Orders", "Aggregate Revenue"])
    wf.add_task(Task(name="Compute Funnel Metrics",  fn=compute_funnel_metrics), depends_on=["Build Click Features", "Aggregate Revenue"])

    # --- Layer 6: Outputs ---
    wf.add_task(Task(name="Executive Report",     fn=generate_executive_report),   depends_on=["Compute RFM Segments", "Compute Funnel Metrics"])
    wf.add_task(Task(name="Marketing Segments",   fn=generate_marketing_segments), depends_on=["Compute RFM Segments"])
    wf.add_task(Task(name="Export Predictions",   fn=export_predictions_to_db),    depends_on=["Train Churn Model", "Train Recommender"])
    wf.add_task(Task(name="Publish Dashboards",   fn=publish_dashboard_data),      depends_on=["Aggregate Revenue", "Compute Funnel Metrics"])
    wf.add_task(Task(name="Send Slack Alerts",    fn=send_slack_alerts),           depends_on=["Executive Report"])

    # --- Layer 7: Finalization ---
    wf.add_task(Task(name="Data Quality Audit",   fn=run_data_quality_audit), depends_on=["Export Predictions", "Publish Dashboards", "Marketing Segments"])
    wf.add_task(Task(name="Archive Raw Data",     fn=archive_raw_data),       depends_on=["Data Quality Audit"])
    wf.add_task(Task(name="Log Pipeline Metadata", fn=log_pipeline_metadata), depends_on=["Data Quality Audit", "Send Slack Alerts"])

    return wf


# =============================================================================
#  Main
# =============================================================================

def main():
    print("\n" + "=" * 72)
    print("  FlowWeaver v0.2.0 — Large DAG Visualization Demo")
    print("=" * 72)

    wf = build_big_workflow()
    tasks = wf.get_all_tasks()
    plan = wf.get_execution_plan()

    print(f"\n  Tasks : {len(tasks)}")
    print(f"  Layers: {len(plan)}")
    for i, layer in enumerate(plan, 1):
        names = [t.name for t in layer]
        print(f"    Layer {i} ({len(layer)} tasks): {names}")

    # Execute
    print(f"\n  Running pipeline...")
    executor = SequentialExecutor()
    executor.execute(wf)

    stats = wf.get_workflow_stats()
    print(f"  ✅ {stats['completed']}/{stats['total_tasks']} completed in {stats['total_time_seconds']:.3f}s")

    # Simulate a couple of mixed statuses so the graph is more interesting
    wf.get_task("Send Slack Alerts").status = TaskStatus.FAILED
    wf.get_task("Send Slack Alerts").error = "Slack API 429 rate limit"
    wf.get_task("Log Pipeline Metadata").status = TaskStatus.PENDING
    wf.get_task("Archive Raw Data").status = TaskStatus.RUNNING

    # Print Mermaid markup
    print("\n📊 Mermaid Diagram:\n")
    print(export_mermaid(wf, orientation="LR"))

    # Save to file
    save_mermaid(wf, "pipeline_diagram.md", orientation="LR")

    # Open colorful graph in browser
    path = view_mermaid(wf, orientation="LR")
    print(f"\n  HTML file: {path}")

    print("\n" + "=" * 72)
    print("  Done! Check your browser for the interactive diagram.")
    print("=" * 72 + "\n")


if __name__ == "__main__":
    main()
