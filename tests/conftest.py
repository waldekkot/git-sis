"""Add app/ to sys.path so 'from lib.xxx import ...' works in all tests."""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "app"))
