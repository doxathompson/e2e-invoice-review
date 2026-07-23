import sys
from pathlib import Path

import nest_asyncio

sys.path.append(str((REPO_ROOT := Path(__file__).resolve().parents[1]) / "backend"))

from app.pipeline.classification import DocumentClassifier

nest_asyncio.apply()


def main() -> None:
    document_path = REPO_ROOT / "samples" / "sample-invoice.pdf"
    classification = DocumentClassifier().run(document_path)
    print(classification.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
