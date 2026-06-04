## Windows Terminal + PowerShell 7 Manual Verification

Run these checks on Windows Terminal with PowerShell 7 after installing the changed Deepy build.

## Prompt Newline

1. Start `deepy` in Windows Terminal under PowerShell 7.
2. Confirm the prompt help mentions `Ctrl+J` for newline on Windows.
3. Type a first line in the prompt.
4. Press Ctrl+J.
5. Expected result:
   - A newline is inserted into the prompt buffer.
   - The prompt is not submitted.
6. Press Enter.
7. Expected result:
   - The prompt submits.
8. Shift+Enter is not a supported Windows requirement for this change.

## CRLF Unicode Modify

1. Create `unicode_demo.py` with CRLF line endings and Unicode text:

   ```python
   def demo():
       title = "中文和Unicode字符演示程序"
       return title
   ```

2. Ask Deepy to replace the Chinese title with English using `modify`.
3. Expected result:
   - The edit succeeds instead of returning `old_string not found in file`.
   - The file keeps single CRLF line endings.
   - The file does not gain extra blank lines after repeated reads/edits.

## Windows Editor-Readable Unicode Creation

1. Ask Deepy to create a new Python file containing Chinese comments through the managed modify/write path.
2. Open the file in Windows Notepad and a common IDE such as VS Code or PyCharm.
3. Expected result:
   - Chinese text displays correctly in Notepad.
   - Chinese text displays correctly in the IDE.
   - The file is identified as UTF-8, with signature when created on Windows and containing non-ASCII text.
4. PowerShell `cat` under a GBK-configured output path is not the compatibility target for this check.

## GBK-Compatible CRLF Modify

1. Create a GBK/GB18030 encoded text file with CRLF line endings:

   ```text
   标题=中文
   城市=北京
   ```

2. Ask Deepy to replace the Chinese labels/values with English using `modify`.
3. Expected result:
   - The edit succeeds.
   - Tool metadata keeps `encoding="gb18030"` and `line_endings="CRLF"`.
   - Reopening the file with GBK/GB18030 decoding shows the replacement without mojibake.

## Stale Delete/Recreate Recovery

1. Create and read a file in Deepy.
2. Delete the file outside Deepy's managed write path.
3. Ask Deepy to recreate it through `modify(content=...)`.
4. Expected result:
   - Deepy preserves stale-write protection.
   - The error message or metadata explains that the file changed after read.
   - The model should re-read or use a managed full-file replacement path before destructive recovery, not shell here-string recreation.
