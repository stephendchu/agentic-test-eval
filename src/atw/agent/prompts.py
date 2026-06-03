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
