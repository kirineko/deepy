## Windows Manual Verification

Use Windows Terminal with PowerShell 7.

1. Start Deepy from a project directory.
2. Ask Deepy to run:
   ```powershell
   wsl.exe --status 2>&1
   ```
3. Confirm the `[Shell]` output renders readable Chinese text instead of mojibake.
4. In the prompt, type a first line, press Ctrl+J, type a second line, then
   press Enter.
5. Confirm the prompt submits one message containing both lines.
6. Confirm Shift+Enter and Ctrl+Enter are not advertised as newline shortcuts.
7. Confirm plain Enter still submits the prompt and does not insert a newline.

No `chcp`, PowerShell profile edits, or global terminal encoding changes should
be required.
