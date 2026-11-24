"""Train the TF-IDF router baseline (D1-R4, FR-DATA-06).

Run from backend/ after `python -m scripts.augment_questions`:
    python -m scripts.train_baseline

Character n-grams (2 to 5, inside word boundaries) + logistic regression. Prints accuracy and
macro-F1 on val.csv and on the hand-written test.csv, plus how often out-of-scope questions are
labelled `other`. Saves data/models/tfidf_router.joblib ({"pipeline", "labels"}).
"""

import argparse
import csv
import sys
from pathlib import Path

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.pipeline import Pipeline

from app.config import BACKEND_DIR, Settings
from app.infrastructure.ml.text import normalize_text

QUESTIONS_DIR = BACKEND_DIR / "data" / "questions"


def read_xy(path: Path, label_column: str = "label") -> tuple[list[str], list[str]]:
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    return [r["text"] for r in rows], [r.get(label_column, "other") for r in rows]


def build_pipeline() -> Pipeline:
    return Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    preprocessor=normalize_text,
                    analyzer="char_wb",
                    ngram_range=(2, 5),
                    sublinear_tf=True,
                    min_df=1,
                ),
            ),
            ("clf", LogisticRegression(max_iter=2000, class_weight="balanced", C=10.0)),
        ]
    )


def report(name: str, pipeline: Pipeline, texts: list[str], labels: list[str]) -> float:
    predicted = pipeline.predict(texts)
    acc = accuracy_score(labels, predicted)
    f1 = f1_score(labels, predicted, average="macro")
    print(f"{name:<6} accuracy {acc:6.1%}   macro-F1 {f1:6.1%}   ({len(texts)} questions)")
    return acc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", type=Path, default=QUESTIONS_DIR / "train.csv")
    parser.add_argument("--val", type=Path, default=QUESTIONS_DIR / "val.csv")
    parser.add_argument("--out", type=Path, default=None, help="default: TFIDF_MODEL_PATH")
    args = parser.parse_args()
    train_path, val_path = args.train, args.val
    if not train_path.exists():
        print("train.csv not found: run python -m scripts.augment_questions first")
        return 1
    x_train, y_train = read_xy(train_path)
    x_val, y_val = read_xy(val_path)
    x_test, y_test = read_xy(QUESTIONS_DIR / "test.csv")
    x_oos, _ = read_xy(QUESTIONS_DIR / "out_of_scope.csv")

    pipeline = build_pipeline()
    pipeline.fit(x_train, y_train)

    print(f"trained on {len(x_train)} questions, {len(set(y_train))} labels")
    report("val", pipeline, x_val, y_val)
    report("test", pipeline, x_test, y_test)
    oos_other = sum(1 for p in pipeline.predict(x_oos) if p == "other") / len(x_oos)
    print(f"out-of-scope labelled `other`: {oos_other:.0%} ({len(x_oos)} questions)")

    probs = pipeline.predict_proba(x_test).max(axis=1)
    threshold = Settings().router_confidence_threshold
    print(f"test questions below ROUTER_CONFIDENCE_THRESHOLD {threshold}: {(probs < threshold).mean():.0%}")
    print("\nper label on test.csv:")
    print(classification_report(y_test, pipeline.predict(x_test), digits=2, zero_division=0))

    out = (args.out or Settings().tfidf_model_path).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"pipeline": pipeline, "labels": list(pipeline.classes_)}, out)
    print(f"saved {out.relative_to(BACKEND_DIR)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
