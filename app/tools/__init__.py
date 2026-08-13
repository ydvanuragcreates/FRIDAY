from app.tools.create_file import create_file
from app.tools.list_files import list_files
from app.tools.read_file import read_file
from app.tools.run_command import run_command
from app.tools.run_tests import run_tests
from app.tools.search_code import search_code
from app.tools.semantic_code_search import semantic_code_search
from app.tools.write_file import write_file

# Read-only / non-destructive tools: safe to bind to the free-roaming
# repository-analysis loop. run_command and run_tests can't modify the
# workspace — they're restricted to an allowlist of test/build/inspection
# commands (see app/core/command_safety.py) — so letting the analysis
# agent run them (e.g. "run the test suite to see the current baseline")
# is no more dangerous than letting it read files. semantic_code_search
# only reads from the (separately maintained) vector index, never the
# workspace directly.
INVESTIGATION_TOOLS = [
    list_files,
    read_file,
    search_code,
    run_command,
    run_tests,
    semantic_code_search,
]

# Tools that write to the filesystem. Never bound to the investigation
# loop. They're used two ways: (a) to propose changes, where the LLM's
# tool-call args are captured and diffed without being executed, and
# (b) to actually apply an already human-approved change.
WRITE_TOOLS = [create_file, write_file]

ALL_TOOLS = INVESTIGATION_TOOLS + WRITE_TOOLS
