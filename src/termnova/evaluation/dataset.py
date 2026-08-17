"""Dataset loader and validator for the Termnova evaluation benchmark."""

import json
from pathlib import Path

from termnova.evaluation import EvalSample


class EvalDatasetLoader:
    """Loads and validates curated evaluation benchmark datasets."""

    @staticmethod
    def load(file_path: Path | str) -> list[EvalSample]:
        """Parse JSON evaluation dataset."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Evaluation dataset file not found at: {path}")

        with open(path, encoding="utf-8") as f:
            raw_data = json.load(f)

        if not isinstance(raw_data, list):
            raise ValueError("Evaluation dataset must be a JSON list of test cases.")

        samples: list[EvalSample] = []
        for idx, item in enumerate(raw_data):
            if not isinstance(item, dict):
                continue

            sample = EvalSample(
                id=str(item.get("id", f"sample_{idx + 1}")),
                query=str(item["query"]),
                ground_truth_answer=str(item.get("ground_truth_answer", "")),
                ground_truth_contexts=[str(c) for c in item.get("ground_truth_contexts", [])],
                source_document=str(item.get("source_document", "")),
                source_page=int(item.get("source_page", 1)),
                difficulty=str(item.get("difficulty", "medium")),
                category=str(item.get("category", "extraction")),
            )
            samples.append(sample)

        return samples
