"""Запуск CLI через python -m tag_summary."""

from __future__ import annotations

import sys

from tag_summary.adapters.cli import main


if __name__ == "__main__":
    sys.exit(main())
