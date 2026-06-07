#!/usr/bin/env python3
# Sisyphus 1.0.0
# Copyright (c) 2026 Шамаев Илья Сергеевич (Yala, @yalayoloyellow). Personal use only.

"""
launch.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
sys.path.insert(0, HERE)

os.execv(sys.executable, [sys.executable, "-m", "sisyphus"] + sys.argv[1:])
