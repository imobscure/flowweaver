#!/usr/bin/env python3
"""
Use Case 2: Machine Learning Pipeline

Demonstrates a real ML workflow with:
- Data preprocessing
- Feature engineering
- Model training
- Model evaluation
- Results reporting
"""

import sys
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from flowweaver import Task, Workflow, SequentialExecutor


# ==================== ML Pipeline Functions ====================


def load_raw_data() -> dict:
    """Load raw training data."""
    print("  └─ Loading raw data...")
    # Simulate data loading
    data = {
        "train_size": 800,
        "test_size": 200,
        "features": 10,
        "samples": [
            {"features": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10], "label": "A"},
            {"features": [2, 3, 4, 5, 6, 7, 8, 9, 10, 11], "label": "B"},
        ],
    }
    return data


def preprocess_data(raw_data: dict) -> dict:
    """Preprocess and clean data."""
    print("  └─ Preprocessing data...")
    # Simulate preprocessing
    raw_data["preprocessed"] = True
    raw_data["missing_values_filled"] = 0
    raw_data["outliers_removed"] = 5
    return raw_data


def engineer_features(preprocessed_data: dict) -> dict:
    """Create new features from raw features."""
    print("  └─ Engineering features...")
    preprocessed_data["engineered"] = True
    preprocessed_data["new_features_created"] = 3
    preprocessed_data["total_features_now"] = 13
    return preprocessed_data


def split_train_test(engineered_data: dict) -> dict:
    """Split data into training and test sets."""
    print("  └─ Splitting train/test...")
    engineered_data["train_samples"] = 640
    engineered_data["test_samples"] = 160
    engineered_data["validation_samples"] = 50
    return engineered_data


def train_model(split_data: dict) -> dict:
    """Train the ML model."""
    print("  └─ Training model (this could take a while)...")
    # Simulate training
    return {
        "model_type": "RandomForest",
        "hyperparameters": {
            "n_estimators": 100,
            "max_depth": 10,
        },
        "training_time_seconds": 12.34,
        "training_samples": split_data.get("train_samples", 640),
    }


def validate_model(model_info: dict) -> dict:
    """Validate model on validation set."""
    print("  └─ Validating model...")
    return {
        "accuracy": 0.95,
        "precision": 0.92,
        "recall": 0.93,
        "f1_score": 0.925,
        "validation_status": "passed",
    }


def evaluate_model(trained_model: dict, model_validation: dict) -> dict:
    """Evaluate model on test set."""
    print("  └─ Evaluating on test set...")
    return {
        "test_accuracy": 0.94,
        "test_precision": 0.91,
        "test_recall": 0.92,
        "test_f1": 0.915,
        "confusion_matrix": [[145, 15], [8, 152]],
        "evaluation_status": "success",
    }


def generate_report(trained_model: dict, validation: dict, evaluation: dict) -> dict:
    """Generate comprehensive ML report."""
    print("  └─ Generating report...")
    report = {
        "timestamp": datetime.now().isoformat(),
        "model_summary": trained_model,
        "validation_metrics": validation,
        "test_metrics": evaluation,
        "recommendation": "Model ready for production deployment",
        "next_steps": [
            "Deploy to staging environment",
            "A/B test against baseline",
            "Monitor performance in production",
        ],
    }

    # Save report
    report_file = Path("ml_report.json")
    with open(report_file, "w") as f:
        json.dump(report, f, indent=2)

    print(f"    ✓ Report saved to {report_file}")
    return report


def run_ml_pipeline():
    """Execute the ML pipeline."""
    print("\n" + "=" * 70)
    print("🤖 MACHINE LEARNING PIPELINE EXAMPLE")
    print("=" * 70 + "\n")

    workflow = Workflow(name="ML Pipeline")

    # Define base task
    load_data = Task(name="load_data", fn=load_raw_data)

    # Create wrapper functions that access workflow results
    def preprocess_wrapper():
        raw = workflow.get_task_result("load_data")
        return preprocess_data(raw)

    def engineer_wrapper():
        preprocessed = workflow.get_task_result("preprocess")
        return engineer_features(preprocessed)

    def split_wrapper():
        engineered = workflow.get_task_result("engineer_features")
        return split_train_test(engineered)

    def train_wrapper():
        split_result = workflow.get_task_result("split_data")
        return train_model(split_result)

    def validate_wrapper():
        model_info = workflow.get_task_result("train_model")
        return validate_model(model_info)

    def evaluate_wrapper():
        model_info = workflow.get_task_result("train_model")
        return evaluate_model(model_info, {})

    def report_wrapper():
        model_info = workflow.get_task_result("train_model")
        validation = workflow.get_task_result("validate_model")
        evaluation = workflow.get_task_result("evaluate_model")
        return generate_report(model_info, validation, evaluation)

    # Define tasks
    preprocess = Task(name="preprocess", fn=preprocess_wrapper)
    engineer = Task(name="engineer_features", fn=engineer_wrapper)
    split = Task(name="split_data", fn=split_wrapper)
    train = Task(name="train_model", fn=train_wrapper, timeout=60.0)
    validate = Task(name="validate_model", fn=validate_wrapper)
    evaluate = Task(name="evaluate_model", fn=evaluate_wrapper)
    report = Task(name="generate_report", fn=report_wrapper)

    # Build workflow
    workflow.add_task(load_data)
    workflow.add_task(preprocess, depends_on=["load_data"])
    workflow.add_task(engineer, depends_on=["preprocess"])
    workflow.add_task(split, depends_on=["engineer_features"])
    workflow.add_task(train, depends_on=["split_data"])
    workflow.add_task(validate, depends_on=["train_model"])
    workflow.add_task(evaluate, depends_on=["train_model"])
    workflow.add_task(report, depends_on=["validate_model", "evaluate_model"])

    # Show execution plan
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
    print(f"\n✅ ML Pipeline Complete!")
    print(f"  Total Tasks: {stats['total_tasks']}")
    print(f"  Completed: {stats['completed']}")
    print(f"  Execution Time: {stats['total_time_seconds']:.3f}s")

    # Show model evaluation
    evaluation = workflow.get_task_result("evaluate_model")
    print(f"\n📊 Model Performance:")
    print(f"  Test Accuracy: {evaluation['test_accuracy']:.2%}")
    print(f"  Test Precision: {evaluation['test_precision']:.2%}")
    print(f"  Test F1-Score: {evaluation['test_f1']:.3f}")


if __name__ == "__main__":
    run_ml_pipeline()
    print("\n" + "=" * 70 + "\n")
