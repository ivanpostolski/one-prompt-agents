# Autonomous file summariser

You have access to file-system tools via `filesystem-mcp-server`.

Goal: produce `files_summary.txt` containing one-line summaries of **every** file
you can read.

Procedure:

1. Build a **plan** where each step reads exactly one file and appends its summary to `files_summary.txt`.
2. Execute the plan step-by-step.
3. After finishing, set `plan_completion_percentage` to **100.0**.
