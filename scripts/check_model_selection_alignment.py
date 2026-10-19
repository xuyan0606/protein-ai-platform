#!/usr/bin/env python3
"""Fail a release when the pinned chat model differs across backend and frontend."""

import argparse
from pathlib import Path


DEFAULT_ID = "gpt6-sol"
NATIVE_MODEL = "gpt-6-sol"
DISPLAY_NAME = "GPT-6-sol"


def check_alignment(root):
    checks = {
        "backend default": ("backend/app/core/config.py", 'LLM_MODEL: str = "gpt-6-sol"'),
        "backend relay model": ("backend/app/core/config.py", 'KUAPAO_GPT6_SOL_MODEL: str = "gpt-6-sol"'),
        "backend registry": ("backend/app/core/llm_registry.py", 'id="gpt6-sol"'),
        "backend relay route": ("backend/app/core/llm_registry.py", "model=settings.KUAPAO_GPT6_SOL_MODEL"),
        "frontend default": ("frontend/src/stores/chat.ts", "return saved || 'gpt6-sol'"),
        "frontend preferred": ("frontend/src/stores/chat.ts", "m.id === 'gpt6-sol' && m.available"),
        "frontend display": ("frontend/src/components/chat/ChatInput.tsx", "currentModel?.name || 'GPT-6-sol'"),
    }
    failures = []
    for label, (relative_path, required) in checks.items():
        path = root / relative_path
        if not path.is_file() or required not in path.read_text(encoding="utf-8"):
            failures.append(label)
    return failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    args = parser.parse_args()
    failures = check_alignment(args.root)
    if failures:
        print("model selection mismatch: " + ", ".join(failures))
        return 1
    print("model selection aligned: {} / {} / {}".format(DEFAULT_ID, NATIVE_MODEL, DISPLAY_NAME))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
