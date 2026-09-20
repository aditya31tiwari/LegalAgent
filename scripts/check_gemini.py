"""Show which Gemini model will be used by the local prototype."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from legalagent.core.gemini import GeminiConfigurationError, choose_model, list_models


def main() -> None:
    try:
        models = list_models()
        print("Available text-generation models:")
        for model in models:
            print(f"- {model}")
        print(f"\nSelected model: {choose_model(models)}")
    except GeminiConfigurationError as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()