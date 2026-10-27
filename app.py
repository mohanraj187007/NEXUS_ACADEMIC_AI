"""
Root Launcher for Academic Attendance Pattern & Risk Analytics System
Enables running `streamlit run app.py` directly from the workspace root.
"""
import os
import sys

# Add nested project directory to path and change directory
nested_project_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "project1")
if os.path.exists(nested_project_dir):
    os.chdir(nested_project_dir)
    if nested_project_dir not in sys.path:
        sys.path.insert(0, nested_project_dir)

# Run the master app
with open(os.path.join(nested_project_dir, "app.py"), "r", encoding="utf-8") as f:
    code = compile(f.read(), "app.py", "exec")
    exec(code, globals())
