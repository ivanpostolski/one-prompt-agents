# StartAndWait Agent prompt

You can use file-system tools (`filesystem-mcp-server`) **and** the tools exposed
by `AutoFilesystemAgent_mcp`.

Goal:

1. If `files_summary.txt` exists in the root directory, delete it.
2. Call `_start_and_wait_AutoFilesystemAgent` (from `AutoFilesystemAgent`) with the prompt
   "Summarise every file you can access" and your own `JOB_ID` to wait until it
   finishes.
3. Verify that `files_summary.txt` now exists and report success or failure.

Return JSON must follow `StartAndWaitAgentResponse` schema and include:
* A detailed `plan` covering each step (delete file, start&wait, verify).
* `plan_completion_percentage` (100.0 when done).
* `content` – "files_summary.txt exists" or an error message. 