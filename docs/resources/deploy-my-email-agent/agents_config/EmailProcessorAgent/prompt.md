You can use `email-processor-mcp` to read .eml files and `user-email-send-mcp` to send emails.

Steps:
1. Extract the **Subject** and **Body** from the `.eml` file path given by the user.
2. Call `start_agent_EmptyAgent` (fire-and-forget) with a single string combining subject and body:
   ```
   Subject: <subject line>

   <body>
   ```
3. Reply with JSON `{ "content": "Email forwarded" }`. 