"""Prepare tests package."""

import os
import sys

# Add project root directory to sys.path.
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
