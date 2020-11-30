"""Language specific actions."""
import glob
import os

all_plugin_files = [
    os.path.splitext(os.path.basename(filename))[0]
    for filename in glob.glob(os.path.join(os.path.dirname(__file__), "*.py"))
]
__all__ = all_plugin_files