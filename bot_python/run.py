#!/usr/bin/env python3
"""
Entry point para ejecutar el bot directamente desde enzonic.

Uso:
    python3 -m bot_python.run              # PAPER (sin token)
    DERIV_TOKEN=xxx python3 -m bot_python.run  # DEMO
"""

import os
import sys

# Permite ejecutar como módulo: python3 -m bot_python.run
if __package__ is None or __package__ == "":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from bot_python.bot_1hz50v import main
else:
    from .bot_1hz50v import main

if __name__ == "__main__":
    main()
