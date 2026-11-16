"""Pre-download BAAI/bge-m3 model weights for offline/container deployment.

Usage:
    python scripts/download_model.py [--cache-dir /app/models] [--model BAAI/bge-m3]
"""

import argparse
import sys
import time


def main() -> int:
    parser = argparse.ArgumentParser(description="Download embedding model weights.")
    parser.add_argument(
        "--cache-dir",
        default="/app/models",
        help="Directory to store model weights (default: /app/models)",
    )
    parser.add_argument(
        "--model",
        default="BAAI/bge-m3",
        help="HuggingFace model identifier (default: BAAI/bge-m3)",
    )
    args = parser.parse_args()

    print(f"Downloading {args.model} into {args.cache_dir}...")
    start = time.perf_counter()

    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(args.model, cache_folder=args.cache_dir)
    test_vec = model.encode(["warmup test string"], convert_to_numpy=True)

    elapsed = time.perf_counter() - start
    print(
        f"Model {args.model} successfully loaded in {elapsed:.1f}s. "
        f"Output dimension: {test_vec.shape[1]}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
