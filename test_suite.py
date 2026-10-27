"""
Root Test Runner for Academic Attendance Pattern & Risk Analytics System
Enables running `python test_suite.py` directly from the workspace root.
"""
import os
import sys

nested_project_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "project1")
if os.path.exists(nested_project_dir):
    os.chdir(nested_project_dir)
    if nested_project_dir not in sys.path:
        sys.path.insert(0, nested_project_dir)

# Execute test suite
import unittest
test_file = os.path.join(nested_project_dir, "test_suite.py")
with open(test_file, "r", encoding="utf-8") as f:
    code = compile(f.read(), "test_suite.py", "exec")
    exec(code, globals())
