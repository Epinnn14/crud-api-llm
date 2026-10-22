import os
import tempfile

# Every test run gets its own throwaway database file.
os.environ["TASKS_DB"] = os.path.join(tempfile.mkdtemp(), "test-tasks.db")
