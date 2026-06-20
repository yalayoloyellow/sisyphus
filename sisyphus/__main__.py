#!/usr/bin/env python3
# Sisyphus 1.1
# Copyright (c) 2026 Шамаев Илья Сергеевич (Yala, @yalayoloyellow). Personal use only.

"""
Entry point for `python -m sisyphus` (Sisyphus 1.1)

Minimal launcher for the REPL.
"""

from .cli.repl import main

if __name__ == "__main__":
    import sys
    main(sys.argv)
