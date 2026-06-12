"""Prompts shared by every arm (held constant — only the toolset varies)."""

TASK = """You are writing the test(s) a maintainer would add for a production \
code change in this repository. The repository is checked out in your working \
directory at the state *before* the change.

Here is the production diff that was made:

<diff>
{prod_diff}
</diff>

Write the pytest test(s) that should accompany this change, matching THIS \
repository's own conventions — naming, fixtures, assertions, mocking, file \
structure. First study how this repository tests similar code — its related \
tests, fixtures, and helpers — using the tools available to you, then write the \
test to match.

Output ONLY the final test file content inside a single ```python code block. \
No explanation outside the code block."""

# v2 protocol: test file for the changed code has been removed from the working
# directory; the agent must discover where tests live and what conventions apply.
# Version control history is not available (git is stripped from the worktree).
# The first line of the code block must declare the intended file path.
TASK_V2 = """You are writing the test(s) a maintainer would add for a production \
code change in this repository. The repository is checked out in your working \
directory at the state *before* the change. Version-control history is not \
available in this working directory.

Here is the production diff that was made:

<diff>
{prod_diff}
</diff>

Write the pytest test(s) that should accompany this change, matching THIS \
repository's own conventions — naming, fixtures, assertions, mocking, file \
structure. First study how this repository tests similar code — its related \
tests, fixtures, and helpers — using the tools available to you, then write the \
test to match.

Output ONLY the final test file content inside a single ```python code block. \
The FIRST LINE inside the code block must be a comment declaring where this test \
file belongs, for example: `# target file: tests/unit/test_example.py`
No explanation outside the code block."""
