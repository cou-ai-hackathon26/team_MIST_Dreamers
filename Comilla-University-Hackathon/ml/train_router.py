"""Fine-tune BanglaBERT as the 9-way service router (D1-T6, FR-DATA-07).

Runs on a normal PC (CPU, about 10 to 20 minutes) or on Colab (GPU, a few minutes); a GPU is
used automatically when PyTorch sees one. Plain PyTorch loop: no `datasets` / `accelerate` needed.

Run from the repository root, with the backend venv active:
    python ml/train_router.py                       # 4 epochs, saves backend/data/models/router/
    python ml/train_router.py --epochs 1 --limit 64  # quick smoke run

Needs: torch, transformers, scikit-learn and the BanglaBERT normaliser
(`pip install git+https://github.com/csebuetnlp/normalizer`). The first run downloads
csebuetnlp/banglabert (about 440 MB) into backend/data/models/hf_cache (git-ignored).

Steps: normalise text -> tokenise (max length 64) -> train with AdamW + linear warm-up ->
evaluate on val.csv after every epoch -> keep the epoch with the best macro-F1 -> report the
hand-written test.csv with the kept model -> save model, tokenizer and labels.json.
"""

import argparse
import csv
import json
import os
import random
import shutil
import sys
import time
from pathlib import Path

import numpy as np
import torch
from normalizer import normalize
from sklearn.metrics import accuracy_score, classification_report, f1_score
from transformers import AutoModelForSequenceClassification, AutoTokenizer, get_linear_schedule_with_warmup

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = ROOT / "backend" / "data" / "questions"
MODELS = ROOT / "backend" / "data" / "models"
BASE_MODEL = "csebuetnlp/banglabert"


def read_csv(path: Path) -> tuple[list[str], list[str]]:
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    return [r["text"] for r in rows], [r["label"] for r in rows]


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def encode(tokenizer, texts: list[str], max_length: int) -> dict[str, torch.Tensor]:  # type: ignore[no-untyped-def]
    return tokenizer(
        [normalize(t) for t in texts],
        max_length=max_length,
        truncation=True,
        padding="max_length",
        return_tensors="pt",
    )


@torch.no_grad()
def predict(model, batch: dict[str, torch.Tensor], device: str, batch_size: int = 64) -> np.ndarray:  # type: ignore[no-untyped-def]
    model.eval()
    out = []
    n = batch["input_ids"].shape[0]
    for start in range(0, n, batch_size):
        part = {k: v[start : start + batch_size].to(device) for k, v in batch.items()}
        out.append(model(**part).logits.argmax(dim=-1).cpu().numpy())
    return np.concatenate(out)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--max-length", type=int, default=64)
    parser.add_argument("--limit", type=int, default=0, help="use only this many training rows (smoke run)")
    parser.add_argument("--out", type=Path, default=MODELS / "router")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--train", type=Path, default=QUESTIONS / "train.csv")
    parser.add_argument("--val", type=Path, default=QUESTIONS / "val.csv")
    args = parser.parse_args()

    set_seed(args.seed)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cpu":
        torch.set_num_threads(os.cpu_count() or 4)
    print(f"device: {device}  threads: {torch.get_num_threads()}")

    x_train, y_train = read_csv(args.train)
    x_val, y_val = read_csv(args.val)
    x_test, y_test = read_csv(QUESTIONS / "test.csv")
    if args.limit:
        order = random.sample(range(len(x_train)), min(args.limit, len(x_train)))
        x_train, y_train = [x_train[i] for i in order], [y_train[i] for i in order]
    labels = sorted(set(y_train) | set(y_val) | set(y_test))
    label_id = {label: i for i, label in enumerate(labels)}
    print(f"train {len(x_train)}  val {len(x_val)}  test {len(x_test)}  labels {len(labels)}")

    cache = MODELS / "hf_cache"
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, cache_dir=cache)
    model = AutoModelForSequenceClassification.from_pretrained(
        BASE_MODEL,
        num_labels=len(labels),
        id2label=dict(enumerate(labels)),
        label2id=label_id,
        cache_dir=cache,
    ).to(device)

    train_enc = encode(tokenizer, x_train, args.max_length)
    train_y = torch.tensor([label_id[y] for y in y_train])
    val_enc = encode(tokenizer, x_val, args.max_length)
    test_enc = encode(tokenizer, x_test, args.max_length)

    steps_per_epoch = (len(x_train) + args.batch_size - 1) // args.batch_size
    total_steps = steps_per_epoch * args.epochs
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    scheduler = get_linear_schedule_with_warmup(optimizer, int(0.1 * total_steps), total_steps)

    best_f1, best_epoch = -1.0, 0
    tmp_dir = args.out.with_name(args.out.name + "_tmp")
    started = time.time()
    for epoch in range(1, args.epochs + 1):
        model.train()
        order = torch.randperm(len(x_train))
        loss_sum = 0.0
        for step in range(steps_per_epoch):
            idx = order[step * args.batch_size : (step + 1) * args.batch_size]
            batch = {k: v[idx].to(device) for k, v in train_enc.items()}
            loss = model(**batch, labels=train_y[idx].to(device)).loss
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()
            optimizer.zero_grad()
            loss_sum += loss.item()
            if (step + 1) % 10 == 0 or step + 1 == steps_per_epoch:
                elapsed = time.time() - started
                print(f"  epoch {epoch} step {step + 1}/{steps_per_epoch}  loss {loss_sum / (step + 1):.3f}  "
                      f"{elapsed / 60:.1f} min", flush=True)  # fmt: skip

        predicted = [labels[i] for i in predict(model, val_enc, device)]
        acc = accuracy_score(y_val, predicted)
        f1 = f1_score(y_val, predicted, average="macro")
        print(f"epoch {epoch}: val accuracy {acc:.1%}  macro-F1 {f1:.1%}", flush=True)
        if f1 > best_f1:
            best_f1, best_epoch = f1, epoch
            shutil.rmtree(tmp_dir, ignore_errors=True)
            model.save_pretrained(tmp_dir)
            tokenizer.save_pretrained(tmp_dir)

    # Keep the best epoch only, then report the hand-written test set with it.
    shutil.rmtree(args.out, ignore_errors=True)
    tmp_dir.rename(args.out)
    (args.out / "labels.json").write_text(json.dumps(labels, ensure_ascii=False, indent=1), encoding="utf-8")
    model = AutoModelForSequenceClassification.from_pretrained(args.out).to(device)
    predicted = [labels[i] for i in predict(model, test_enc, device)]
    print(f"\nbest epoch {best_epoch}: val macro-F1 {best_f1:.1%}")
    print(f"test accuracy {accuracy_score(y_test, predicted):.1%}  "
          f"macro-F1 {f1_score(y_test, predicted, average='macro'):.1%}")  # fmt: skip
    print(classification_report(y_test, predicted, digits=2, zero_division=0))
    print(f"saved {args.out}  ({(time.time() - started) / 60:.1f} min)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
