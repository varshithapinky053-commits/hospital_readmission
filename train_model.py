"""
Train a hospital readmission risk prediction model.
Run: python train_model.py
"""

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

MODEL_DIR = Path(__file__).parent / "model"
MODEL_DIR.mkdir(exist_ok=True)

FEATURE_COLUMNS = [
    "age",
    "time_in_hospital",
    "num_lab_procedures",
    "num_procedures",
    "num_medications",
    "num_outpatient",
    "num_inpatient",
    "num_emergency",
    "gender",
    "medical_specialty",
    "primary_diagnosis",
    "insurance_type",
]

CATEGORICAL_COLUMNS = [
    "gender",
    "medical_specialty",
    "primary_diagnosis",
    "insurance_type",
]


def generate_synthetic_data(n_samples=5000, seed=42):
    rng = np.random.default_rng(seed)

    genders = ["Male", "Female"]
    specialties = [
        "Cardiology", "Emergency", "Internal Medicine",
        "Orthopedics", "Surgery", "Pediatrics", "Neurology",
    ]
    diagnoses = [
        "Diabetes", "Heart Failure", "Pneumonia", "COPD",
        "Hypertension", "Kidney Disease", "Stroke", "Sepsis",
    ]
    insurance = ["Medicare", "Medicaid", "Private", "Self-Pay"]

    data = {
        "age": rng.integers(18, 90, n_samples),
        "time_in_hospital": rng.integers(1, 15, n_samples),
        "num_lab_procedures": rng.integers(0, 70, n_samples),
        "num_procedures": rng.integers(0, 7, n_samples),
        "num_medications": rng.integers(1, 25, n_samples),
        "num_outpatient": rng.integers(0, 20, n_samples),
        "num_inpatient": rng.integers(0, 10, n_samples),
        "num_emergency": rng.integers(0, 15, n_samples),
        "gender": rng.choice(genders, n_samples),
        "medical_specialty": rng.choice(specialties, n_samples),
        "primary_diagnosis": rng.choice(diagnoses, n_samples),
        "insurance_type": rng.choice(insurance, n_samples),
    }

    df = pd.DataFrame(data)

    risk_score = (
        (df["age"] - 40) * 0.02
        + df["time_in_hospital"] * 0.08
        + df["num_medications"] * 0.04
        + df["num_inpatient"] * 0.12
        + df["num_emergency"] * 0.06
        + (df["primary_diagnosis"].isin(["Heart Failure", "COPD", "Kidney Disease"])).astype(int) * 0.5
        + rng.normal(0, 0.3, n_samples)
    )
    df["readmitted"] = (risk_score > np.percentile(risk_score, 65)).astype(int)

    return df


def train():
    print("Generating training data...")
    df = generate_synthetic_data()

    encoders = {}
    X = df[FEATURE_COLUMNS].copy()

    for col in CATEGORICAL_COLUMNS:
        le = LabelEncoder()
        X[col] = le.fit_transform(X[col].astype(str))
        encoders[col] = le

    y = df["readmitted"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    print("Training Gradient Boosting model...")
    model = GradientBoostingClassifier(
        n_estimators=150,
        max_depth=4,
        learning_rate=0.1,
        random_state=42,
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, y_prob)

    print(f"\nROC-AUC Score: {auc:.4f}")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, target_names=["Not Readmitted", "Readmitted"]))

    metadata = {
        "feature_columns": FEATURE_COLUMNS,
        "categorical_columns": CATEGORICAL_COLUMNS,
        "model_type": "GradientBoostingClassifier",
        "roc_auc": round(float(auc), 4),
        "risk_thresholds": {"high": 0.7, "medium": 0.4},
        "encoder_classes": {
            col: list(encoders[col].classes_) for col in CATEGORICAL_COLUMNS
        },
    }

    model_path = MODEL_DIR / "readmission_model.pkl"
    encoders_path = MODEL_DIR / "model_metadata.pkl"

    joblib.dump({"model": model, "encoders": encoders}, model_path)
    joblib.dump(metadata, encoders_path)

    print(f"\nModel saved to {model_path}")
    print(f"Metadata saved to {encoders_path}")
    return model, encoders, metadata


if __name__ == "__main__":
    train()
