# BanglaBERT router training (D1-T6, FR-DATA-07)

`train_router.py` fine-tunes [`csebuetnlp/banglabert`](https://huggingface.co/csebuetnlp/banglabert) to sort a question into the 9 labels (8 services + `other`). The app uses it when `ROUTER_BACKEND=banglabert`; everyone else can keep `ROUTER_BACKEND=tfidf`.

## Input and output
- Input: `backend/data/questions/train.csv`, `val.csv` (from `python -m scripts.augment_questions`) and the hand-written `test.csv`.
- Output: `backend/data/models/router/` with the model, the tokenizer and `labels.json`. It is git-ignored (about 450 MB).

## Option A: your own PC (recommended)
No GPU needed. 5 epochs over about 1,000 questions take roughly 10 to 20 minutes on a 6-core CPU.

```powershell
# repository root, backend venv active
pip install git+https://github.com/csebuetnlp/normalizer     # once
$env:PYTHONIOENCODING = "utf-8"
python ml/train_router.py --epochs 5 --lr 3e-5
python ml/train_router.py --epochs 1 --limit 64             # 1-minute smoke run
```

The first run downloads BanglaBERT (about 440 MB) into `backend/data/models/hf_cache/`. If it says it cannot reach huggingface.co, run `Remove-Item Env:HF_HUB_OFFLINE` in that terminal first.

## Option B: Google Colab (if your PC is too slow)
1. Runtime > Change runtime type > T4 GPU.
2. Upload `ml/train_router.py` and the three CSVs, keeping the folder layout `backend/data/questions/`.
3. Run `!pip install transformers scikit-learn git+https://github.com/csebuetnlp/normalizer` and `!python ml/train_router.py --epochs 5 --lr 3e-5`. It uses the GPU automatically.
4. Zip and download `backend/data/models/router/`, then unzip it into the same path on the laptop.

## What it prints
Validation accuracy and macro-F1 after every epoch. It keeps the epoch with the best macro-F1, then prints test accuracy and macro-F1 plus a per-label report. Compare these with the TF-IDF baseline from `python -m scripts.train_baseline`. The full comparison is D2-T1, written to `docs/results/router_eval.md`.

## Sharing the model
Only the demo laptop needs it. Zip `backend/data/models/router/`, share it through Google Drive, and unzip it into the same folder there. Never commit it.
