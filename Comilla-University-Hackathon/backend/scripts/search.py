"""Tries the search index by hand (D1-T2 done-check).

Run from backend/:
    python -m scripts.search "বয়স্ক ভাতার বয়স কত"
    python -m scripts.search "পাসপোর্ট ফি কত" --service e_passport -k 3
"""

import argparse
import sys

from app.config import get_settings
from app.container import Container
from app.domain import policies


def main() -> int:
    parser = argparse.ArgumentParser(description="Search the official passages")
    parser.add_argument("question")
    parser.add_argument("--service", default=None, help="service id to filter by (default: all)")
    parser.add_argument("-k", type=int, default=policies.TOP_K)
    args = parser.parse_args()

    container = Container(get_settings())
    passages = container.retriever.search(args.question, args.service, args.k)
    if not passages:
        print("No passages found. Did you run: python -m scripts.ingest ?")
        return 1
    threshold = container.settings.retrieval_min_score
    print(f"RETRIEVAL_MIN_SCORE = {threshold}\n")
    for i, p in enumerate(passages, 1):
        mark = ">=" if p.score >= threshold else "< "
        first_line = " ".join(p.text.split())[:110]
        print(f"{i}. {p.score:.3f} {mark} {p.chunk_id:24} {p.title}")
        print(f"   {first_line}...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
