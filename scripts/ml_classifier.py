#!/usr/bin/env python3
"""
ML Classifier for Whale Entity Type Prediction

Trains a RandomForest classifier on labeled entities from the knowledge graph
to predict entity_type (fund, individual, bot, protocol) for unknown addresses.

Features extracted from:
  - Knowledge graph: entities, behavioral_fingerprints, relationships, evidence
  - CSV: address_type, borrowed_assets, total_borrowed_m, protocol, etc.

Usage:
  python3 scripts/ml_classifier.py                    # Train + predict
  python3 scripts/ml_classifier.py --train-only       # Train and save model
  python3 scripts/ml_classifier.py --predict-only     # Load model and predict
  python3 scripts/ml_classifier.py --top 20           # Show top N predictions
"""

import argparse
import ast
import json
import os
import sqlite3
import sys
from pathlib import Path

import pandas as pd
import numpy as np
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score, StratifiedKFold
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.preprocessing import LabelEncoder

# ── Paths ──────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "knowledge_graph.db"
CSV_PATH = PROJECT_ROOT / "references" / "top_lending_protocol_borrowers_eoa_safe_with_identity.csv"
MODEL_PATH = PROJECT_ROOT / "data" / "classifier_model.pkl"


# ── Feature Extraction ────────────────────────────────────────────────────────

def load_knowledge_graph() -> dict:
    """Load all relevant data from knowledge graph into dataframes."""
    conn = sqlite3.connect(DB_PATH)

    entities = pd.read_sql_query(
        "SELECT address, identity, entity_type, confidence, cluster_id, "
        "contract_type, ens_name FROM entities",
        conn,
    )

    behavioral = pd.read_sql_query(
        "SELECT address, timezone_signal, gas_strategy, trading_style, "
        "risk_profile FROM behavioral_fingerprints",
        conn,
    )

    # Relationship counts per address (both as source and target)
    rel_counts = pd.read_sql_query(
        """
        SELECT address,
            SUM(temporal_correlation) as temporal_rel_count,
            SUM(same_behavior) as behavior_rel_count,
            SUM(counterparty_overlap) as counterparty_rel_count,
            SUM(total) as total_rel_count
        FROM (
            SELECT source as address,
                SUM(CASE WHEN relationship_type='temporal_correlation' THEN 1 ELSE 0 END) as temporal_correlation,
                SUM(CASE WHEN relationship_type='same_behavior' THEN 1 ELSE 0 END) as same_behavior,
                SUM(CASE WHEN relationship_type='counterparty_overlap' THEN 1 ELSE 0 END) as counterparty_overlap,
                COUNT(*) as total
            FROM relationships GROUP BY source
            UNION ALL
            SELECT target as address,
                SUM(CASE WHEN relationship_type='temporal_correlation' THEN 1 ELSE 0 END),
                SUM(CASE WHEN relationship_type='same_behavior' THEN 1 ELSE 0 END),
                SUM(CASE WHEN relationship_type='counterparty_overlap' THEN 1 ELSE 0 END),
                COUNT(*)
            FROM relationships GROUP BY target
        ) GROUP BY address
        """,
        conn,
    )

    # Evidence counts per address by source type
    evidence_counts = pd.read_sql_query(
        """
        SELECT entity_address as address,
            SUM(CASE WHEN source='ENS' THEN 1 ELSE 0 END) as ens_evidence,
            SUM(CASE WHEN source='Snapshot' THEN 1 ELSE 0 END) as governance_evidence,
            SUM(CASE WHEN source='CIO' THEN 1 ELSE 0 END) as cio_evidence,
            SUM(CASE WHEN source='OSINT' THEN 1 ELSE 0 END) as osint_evidence,
            SUM(CASE WHEN source='Propagation' THEN 1 ELSE 0 END) as propagation_evidence,
            COUNT(*) as total_evidence
        FROM evidence
        GROUP BY entity_address
        """,
        conn,
    )

    conn.close()

    return {
        "entities": entities,
        "behavioral": behavioral,
        "rel_counts": rel_counts,
        "evidence_counts": evidence_counts,
    }


def load_csv_data() -> pd.DataFrame:
    """Load and aggregate CSV data per borrower address."""
    df = pd.read_csv(CSV_PATH)

    def parse_assets(val):
        """Parse borrowed_assets string like \"['USDT', 'WBTC']\" into a list."""
        try:
            return ast.literal_eval(val)
        except (ValueError, SyntaxError):
            return []

    df["asset_list"] = df["borrowed_assets"].apply(parse_assets)
    df["asset_count"] = df["asset_list"].apply(len)

    # Aggregate per borrower across protocols
    agg = df.groupby("borrower").agg(
        address_type=("address_type", "first"),
        total_borrowed_m=("total_borrowed_m", "sum"),
        net_position_m=("net_position_m", "sum"),
        protocol_count=("project", "nunique"),
        protocols=("project", lambda x: list(x.unique())),
        asset_count_total=("asset_count", "sum"),
        unique_assets=("asset_list", lambda x: len(set(a for lst in x for a in lst))),
        has_ens_csv=("ens_name", lambda x: x.notna().any()),
        has_contract_name=("contract_name", lambda x: x.notna().any()),
        has_safe_label=("safe_label", lambda x: x.notna().any()),
        has_mev_label=("mev_label", lambda x: x.notna().any()),
        has_cex_name=("cex_name", lambda x: x.notna().any()),
        csv_identity=("identity", "first"),
        csv_confidence=("confidence", "first"),
    ).reset_index()
    agg = agg.rename(columns={"borrower": "address"})

    # Protocol binary flags
    for proto in ["aave", "spark", "compound", "morpho"]:
        agg[f"uses_{proto}"] = agg["protocols"].apply(lambda x: proto in x)

    return agg


def extract_timezone_offset(tz_signal: str) -> float:
    """Convert 'UTC+7' or 'UTC-3' to numeric offset."""
    if pd.isna(tz_signal) or not isinstance(tz_signal, str):
        return np.nan
    try:
        return float(tz_signal.replace("UTC", "").replace("+", ""))
    except ValueError:
        return np.nan


def build_feature_matrix(kg: dict, csv_data: pd.DataFrame) -> pd.DataFrame:
    """
    Merge knowledge graph + CSV data and extract feature columns.

    Returns a dataframe with one row per address and all features + labels.
    """
    entities = kg["entities"].copy()

    # Merge behavioral fingerprints
    merged = entities.merge(kg["behavioral"], on="address", how="left")

    # Merge relationship counts
    merged = merged.merge(kg["rel_counts"], on="address", how="left")

    # Merge evidence counts
    merged = merged.merge(kg["evidence_counts"], on="address", how="left")

    # Merge CSV data
    merged = merged.merge(csv_data, on="address", how="left")

    # ── Feature Engineering ────────────────────────────────────────────────

    # 1. Address type encoding: EOA=0, Contract=1
    merged["is_contract"] = (merged["address_type"] == "Contract").astype(int)

    # 2. Has ENS (from either KG or CSV)
    merged["has_ens"] = (
        merged["ens_name"].notna() | merged["has_ens_csv"].fillna(False)
    ).astype(int)

    # 3. Is in a cluster
    merged["in_cluster"] = merged["cluster_id"].notna().astype(int)

    # 4. Timezone offset (numeric)
    merged["tz_offset"] = merged["timezone_signal"].apply(extract_timezone_offset)

    # 5. Timezone region buckets (Asia-Pac / Americas / Europe)
    def tz_region(offset):
        if pd.isna(offset):
            return 0  # unknown
        if 5 <= offset <= 12:
            return 1  # Asia-Pacific
        elif -8 <= offset <= -1:
            return 2  # Americas
        elif 0 <= offset <= 4:
            return 3  # Europe/Africa
        return 0

    merged["tz_region"] = merged["tz_offset"].apply(tz_region)

    # 6. Gas strategy encoding
    gas_map = {"low": 0, "medium": 1, "adaptive": 2, "high": 3, "very_high": 4}
    merged["gas_strategy_enc"] = merged["gas_strategy"].map(gas_map).fillna(-1)

    # 7. Trading style encoding
    style_map = {"none": 0, "spot": 1, "leverage": 2, "arbitrage": 3, "mev": 4}
    merged["trading_style_enc"] = merged["trading_style"].map(style_map).fillna(-1)

    # 8. Risk profile encoding
    risk_map = {"unknown": 0, "conservative": 1, "moderate": 2, "aggressive": 3}
    merged["risk_profile_enc"] = merged["risk_profile"].map(risk_map).fillna(-1)

    # 9. Fill NaN numeric columns with 0
    fill_zero_cols = [
        "temporal_rel_count", "behavior_rel_count", "counterparty_rel_count",
        "total_rel_count", "ens_evidence", "governance_evidence", "cio_evidence",
        "osint_evidence", "propagation_evidence", "total_evidence",
        "total_borrowed_m", "net_position_m", "protocol_count",
        "asset_count_total", "unique_assets",
    ]
    for col in fill_zero_cols:
        if col in merged.columns:
            merged[col] = merged[col].fillna(0)

    # 10. Boolean flags to int
    bool_cols = [
        "has_contract_name", "has_safe_label", "has_mev_label",
        "has_cex_name", "uses_aave", "uses_spark", "uses_compound", "uses_morpho",
    ]
    for col in bool_cols:
        if col in merged.columns:
            merged[col] = merged[col].fillna(False).astype(int)

    # 11. Log-scale borrowed (huge range)
    merged["log_borrowed"] = np.log1p(merged["total_borrowed_m"])

    # 12. Net position ratio (net / borrowed, capped at [-1, 1])
    merged["position_ratio"] = np.where(
        merged["total_borrowed_m"] > 0,
        (merged["net_position_m"] / merged["total_borrowed_m"]).clip(-1, 1),
        0,
    )

    return merged


# ── Feature Columns ───────────────────────────────────────────────────────────

FEATURE_COLS = [
    # Core identity signals
    "is_contract",
    "has_ens",
    "in_cluster",
    "has_safe_label",
    "has_mev_label",
    "has_cex_name",
    "has_contract_name",
    # Scale and activity
    "log_borrowed",
    "position_ratio",
    "protocol_count",
    "unique_assets",
    # Behavioral signals
    "tz_region",
    "gas_strategy_enc",
    "trading_style_enc",
    "risk_profile_enc",
    # Graph signals
    "temporal_rel_count",
    "behavior_rel_count",
    "total_evidence",
    "governance_evidence",
    # Protocol usage
    "uses_aave",
    "uses_spark",
    "uses_compound",
    "uses_morpho",
]


# ── Training ──────────────────────────────────────────────────────────────────

def train_model(df: pd.DataFrame) -> tuple:
    """
    Train a RandomForest classifier on labeled data.

    Returns (model, label_encoder, metrics_dict).
    """
    # Filter to labeled entities with known entity_type
    labeled = df[
        (df["entity_type"].notna())
        & (df["entity_type"] != "unknown")
        & (df["entity_type"] != "")
    ].copy()

    print(f"\n{'='*60}")
    print("TRAINING DATA")
    print(f"{'='*60}")
    print(f"Total labeled entities: {len(labeled)}")
    print(f"\nClass distribution:")
    print(labeled["entity_type"].value_counts().to_string())

    # Encode labels
    le = LabelEncoder()
    y = le.fit_transform(labeled["entity_type"])
    print(f"\nClasses: {list(le.classes_)}")

    # Prepare features
    X = labeled[FEATURE_COLS].copy()

    # Fill any remaining NaN with 0
    X = X.fillna(0)

    print(f"Feature matrix shape: {X.shape}")
    print(f"Features: {FEATURE_COLS}")

    # Train RandomForest
    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=10,
        min_samples_leaf=5,
        min_samples_split=10,
        class_weight="balanced",  # handle class imbalance
        random_state=42,
        n_jobs=-1,
    )

    # Cross-validation (stratified to handle imbalance)
    n_splits = min(5, min(labeled["entity_type"].value_counts()))
    if n_splits >= 2:
        cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
        scores = cross_val_score(model, X, y, cv=cv, scoring="f1_weighted")
        print(f"\n{'='*60}")
        print("CROSS-VALIDATION RESULTS")
        print(f"{'='*60}")
        print(f"F1 (weighted) per fold: {[f'{s:.3f}' for s in scores]}")
        print(f"Mean F1: {scores.mean():.3f} (+/- {scores.std():.3f})")
    else:
        print("\nSkipping cross-validation (too few samples in some classes)")

    # Train final model on all labeled data
    model.fit(X, y)

    # Feature importances
    importances = pd.Series(model.feature_importances_, index=FEATURE_COLS)
    importances = importances.sort_values(ascending=False)
    print(f"\n{'='*60}")
    print("FEATURE IMPORTANCES (top 15)")
    print(f"{'='*60}")
    for feat, imp in importances.head(15).items():
        bar = "#" * int(imp * 50)
        print(f"  {feat:25s} {imp:.4f} {bar}")

    # Classification report on training data (for reference)
    y_pred = model.predict(X)
    print(f"\n{'='*60}")
    print("TRAINING SET CLASSIFICATION REPORT")
    print(f"{'='*60}")
    print(classification_report(y, y_pred, target_names=le.classes_))

    metrics = {
        "n_labeled": len(labeled),
        "n_features": len(FEATURE_COLS),
        "classes": list(le.classes_),
        "cv_f1_mean": float(scores.mean()) if n_splits >= 2 else None,
        "feature_importances": importances.to_dict(),
    }

    return model, le, metrics


# ── Prediction ────────────────────────────────────────────────────────────────

def predict_unknowns(
    df: pd.DataFrame,
    model: RandomForestClassifier,
    le: LabelEncoder,
    top_n: int = 30,
) -> pd.DataFrame:
    """
    Predict entity_type for unlabeled/unknown addresses.

    Returns predictions sorted by confidence descending.
    """
    # Filter to unknown entities
    unknown = df[
        (df["entity_type"].isna()) | (df["entity_type"] == "unknown")
    ].copy()

    if len(unknown) == 0:
        print("\nNo unknown entities to predict.")
        return pd.DataFrame()

    X = unknown[FEATURE_COLS].copy().fillna(0)

    # Predict
    pred_labels = model.predict(X)
    pred_proba = model.predict_proba(X)

    unknown = unknown.copy()
    unknown["predicted_type"] = le.inverse_transform(pred_labels)
    unknown["prediction_confidence"] = pred_proba.max(axis=1)

    # Add per-class probabilities
    for i, cls in enumerate(le.classes_):
        unknown[f"prob_{cls}"] = pred_proba[:, i]

    # Sort by confidence
    unknown = unknown.sort_values("prediction_confidence", ascending=False)

    print(f"\n{'='*60}")
    print(f"PREDICTIONS FOR UNKNOWN ADDRESSES (top {top_n})")
    print(f"{'='*60}")
    print(f"Total unknown: {len(unknown)}")
    print(f"\nPredicted distribution:")
    print(unknown["predicted_type"].value_counts().to_string())
    print(f"\nConfidence stats:")
    print(f"  Mean: {unknown['prediction_confidence'].mean():.3f}")
    print(f"  Median: {unknown['prediction_confidence'].median():.3f}")
    print(f"  >80%: {(unknown['prediction_confidence'] > 0.8).sum()}")
    print(f"  >60%: {(unknown['prediction_confidence'] > 0.6).sum()}")

    # Display top predictions
    display_cols = [
        "address", "predicted_type", "prediction_confidence",
        "total_borrowed_m", "unique_assets", "tz_region",
        "has_ens", "has_safe_label", "is_contract",
    ]

    # Map tz_region back to readable
    tz_map = {0: "unknown", 1: "Asia-Pac", 2: "Americas", 3: "Europe"}

    print(f"\n{'='*60}")
    print(f"TOP {top_n} HIGHEST-CONFIDENCE PREDICTIONS")
    print(f"{'='*60}")
    print(f"{'Address':44s} {'Type':12s} {'Conf':6s} {'Borrowed':>10s} {'Assets':>6s} {'Region':10s} {'ENS':>3s} {'Safe':>4s}")
    print("-" * 100)

    for _, row in unknown.head(top_n).iterrows():
        addr = row["address"][:42]
        region = tz_map.get(int(row["tz_region"]), "?")
        borrowed_str = f"${row['total_borrowed_m']:,.0f}M" if row["total_borrowed_m"] > 0 else "-"
        print(
            f"{addr:44s} {row['predicted_type']:12s} {row['prediction_confidence']:.3f} "
            f"{borrowed_str:>10s} {int(row['unique_assets']):>6d} {region:10s} "
            f"{'Y' if row['has_ens'] else 'N':>3s} {'Y' if row['has_safe_label'] else 'N':>4s}"
        )

    # Show class probability breakdown for top 5
    print(f"\n{'='*60}")
    print("CLASS PROBABILITY BREAKDOWN (top 5)")
    print(f"{'='*60}")
    prob_cols = [f"prob_{cls}" for cls in le.classes_]
    for _, row in unknown.head(5).iterrows():
        addr = row["address"][:16] + "..."
        probs = " | ".join(
            f"{cls}: {row[f'prob_{cls}']:.2f}" for cls in le.classes_
        )
        print(f"  {addr}  =>  {probs}")

    return unknown


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="ML classifier for whale entity type prediction"
    )
    parser.add_argument("--train-only", action="store_true", help="Train and save model only")
    parser.add_argument("--predict-only", action="store_true", help="Load saved model and predict")
    parser.add_argument("--top", type=int, default=30, help="Number of top predictions to show")
    parser.add_argument("--output", "-o", type=str, help="Save predictions to CSV")
    args = parser.parse_args()

    # Load data
    print("Loading knowledge graph...")
    kg = load_knowledge_graph()
    print(f"  Entities: {len(kg['entities'])}")
    print(f"  Behavioral fingerprints: {len(kg['behavioral'])}")
    print(f"  With relationships: {len(kg['rel_counts'])}")
    print(f"  With evidence: {len(kg['evidence_counts'])}")

    print("\nLoading CSV data...")
    csv_data = load_csv_data()
    print(f"  Borrowers: {len(csv_data)}")

    print("\nBuilding feature matrix...")
    df = build_feature_matrix(kg, csv_data)
    print(f"  Total rows: {len(df)}")
    print(f"  Labeled (non-unknown): {len(df[(df['entity_type'].notna()) & (df['entity_type'] != 'unknown')])}")
    print(f"  Unknown: {len(df[(df['entity_type'].isna()) | (df['entity_type'] == 'unknown')])}")

    if args.predict_only:
        # Load saved model
        if not MODEL_PATH.exists():
            print(f"\nERROR: No saved model at {MODEL_PATH}. Run training first.")
            sys.exit(1)
        saved = joblib.load(MODEL_PATH)
        model = saved["model"]
        le = saved["label_encoder"]
        print(f"\nLoaded model from {MODEL_PATH}")
    else:
        # Train
        model, le, metrics = train_model(df)

        # Save model
        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {"model": model, "label_encoder": le, "features": FEATURE_COLS, "metrics": metrics},
            MODEL_PATH,
        )
        print(f"\nModel saved to {MODEL_PATH}")

        if args.train_only:
            return

    # Predict unknowns
    predictions = predict_unknowns(df, model, le, top_n=args.top)

    # Save predictions if requested
    if args.output and len(predictions) > 0:
        out_cols = [
            "address", "predicted_type", "prediction_confidence",
            "total_borrowed_m", "net_position_m", "unique_assets",
            "protocol_count", "has_ens", "has_safe_label", "is_contract",
            "tz_region", "temporal_rel_count", "total_evidence",
        ] + [f"prob_{cls}" for cls in le.classes_]

        out_df = predictions[[c for c in out_cols if c in predictions.columns]]
        out_df.to_csv(args.output, index=False)
        print(f"\nPredictions saved to {args.output}")


if __name__ == "__main__":
    main()
