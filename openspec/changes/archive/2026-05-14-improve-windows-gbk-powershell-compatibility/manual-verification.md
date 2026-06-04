## Windows Terminal + PowerShell 7 Manual Verification

Run these checks on a Windows machine using Windows Terminal with PowerShell 7.

## 1. Python Unicode Shell Execution

Start Deepy from PowerShell 7:

```powershell
deepy
```

Ask Deepy to run this through the shell tool:

```text
请使用 shell 工具运行: python -c "print('中文 ✓ emoji-like output')"
```

Expected result:

- The command exits with code 0.
- Output displays the Unicode text.
- No `UnicodeEncodeError`, GBK/ANSI encoding failure, or mojibake appears.

## 2. GBK-Compatible File Modify

Create a GBK/CP936-compatible file from PowerShell:

```powershell
[System.Text.Encoding]::RegisterProvider([System.Text.CodePagesEncodingProvider]::Instance)
[IO.File]::WriteAllText("gbk_probe.txt", "城市=北京`r`n", [Text.Encoding]::GetEncoding(936))
```

In Deepy, ask:

```text
读取 gbk_probe.txt，然后把“北京”修改为“上海”。
```

Verify from PowerShell:

```powershell
[System.Text.Encoding]::RegisterProvider([System.Text.CodePagesEncodingProvider]::Instance)
[IO.File]::ReadAllText("gbk_probe.txt", [Text.Encoding]::GetEncoding(936))
```

Expected result:

- Deepy reads the file as readable Chinese text.
- `modify` succeeds without an `old_string not found` error.
- PowerShell verification prints `城市=上海`.

## 3. Shift+Enter Prompt Newline

In Deepy's prompt:

1. Type `第一行`
2. Press Shift+Enter
3. Type `第二行`
4. Press Enter

Expected result:

- Shift+Enter inserts a newline instead of submitting.
- Enter submits the two-line prompt once.
