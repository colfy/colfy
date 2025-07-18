#!/usr/bin/env python3
"""
Startup script for the original crypto battle bot compatibility layer
"""

import sys
import os

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import and run the original bot
from original_bot import main

if __name__ == "__main__":
    main()