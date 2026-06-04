"""Textual CSS for the Modern (Textual) UI.

Extracted verbatim from ``DeepyTuiApp.CSS`` to keep ``app.py`` focused on
behavior. The string content is preserved exactly so Textual parses it
identically.
"""

from __future__ import annotations

APP_CSS = """
    Screen {
        layout: vertical;
        background: $surface;
    }

    #main-layout {
        height: 1fr;
        layout: horizontal;
    }

    #transcript {
        width: 1fr;
        height: 1fr;
        padding: 0 1;
        overflow-y: auto;
        scrollbar-size-vertical: 1;
    }

    #transcript * {
        link-style: none;
    }

    #side-panel {
        width: 30;
        display: none;
        background: $panel;
        padding: 0 1;
    }

    #side-panel.-visible {
        display: block;
    }

    PromptPanel {
        height: auto;
        padding: 0 1;
        background: $boost;
    }

    #prompt-input {
        height: 4;
        min-height: 4;
        max-height: 4;
        border: none;
        padding: 0;
        background: transparent;
        overflow-y: auto;
    }

    #prompt-input:focus {
        border: none;
    }

    #prompt-images {
        height: 1;
        margin: 0 1 0 1;
        color: $accent;
        display: none;
    }

    #prompt-actions {
        height: 1;
        color: $text-muted;
        display: block;
    }

    #prompt-suggestions {
        height: auto;
        max-height: 6;
        position: absolute;
        offset: 0 -6;
        width: 100%;
        display: none;
        padding: 0 1;
        layer: overlay;
        overlay: screen;
        background: $panel;
    }

    #prompt-suggestions > .option-list--option {
        padding: 0 1;
    }

    #prompt-suggestions > .option-list--option-highlighted {
        color: #ffffff !important;
        background: #414868 !important;
        text-style: bold !important;
    }

    #prompt-suggestions > .option-list--option-disabled {
        color: #7f849c !important;
    }

    #prompt-suggestions > .option-list--option-hover {
        background: #292e42 !important;
    }

    StatusBar {
        height: 1;
        padding: 0 1;
        background: $boost;
    }

    #status-left {
        width: 1fr;
        color: $accent;
    }

    #status-right {
        width: auto;
        color: $text-muted;
    }

    .transcript-block {
        height: auto;
        margin: 0 0 0 0;
        padding: 0 1;
        border-left: none;
    }

    .transcript-block:focus {
        background: $boost;
    }

    .block-title {
        color: $text-muted;
        text-style: none;
        height: 1;
    }

    .role-line {
        height: auto;
        margin: 0;
        padding: 0;
    }

    .role-marker {
        width: 2;
        min-width: 2;
        height: 1;
        text-style: bold;
    }

    .block-body, .block-markdown, .tool-details, #side-status, #prompt-input {
        text-style: none;
    }

    .block-markdown {
        padding: 0;
        margin: 0;
        width: 1fr;
    }

    .block-markdown MarkdownBlock {
        margin: 0;
    }

    .block-markdown MarkdownTable,
    .block-markdown Table {
        margin: 0;
        padding: 0;
    }

    .block-markdown MarkdownTableCell,
    .block-markdown TableCell {
        padding: 0 1;
    }

    .user-block {
        color: $text;
    }

    .user-block .block-title {
        color: $accent;
        text-style: bold;
    }

    .user-block .block-body {
        width: 1fr;
    }

    .info-block {
        color: $text-muted;
        margin: 0;
    }

    .assistant-block {
        color: $text;
        margin: 0 0 1 0;
    }

    .assistant-block Markdown,
    .assistant-block .block-markdown {
        color: $text;
    }

    .assistant-block .block-title {
        color: $secondary;
        text-style: bold;
    }

    .assistant-block.-active .block-title {
        color: $accent;
    }

    .thinking-block {
        color: $text-muted;
        margin: 0;
    }

    .thinking-block .block-title {
        color: $warning;
        text-style: bold;
    }

    .thinking-block .block-body {
        color: $text-muted;
        width: 1fr;
    }

    .tool-block .block-title {
        color: $success;
        text-style: bold;
    }

    .tool-block.-running .block-title {
        color: $accent;
    }

    .tool-block .block-body {
        width: 1fr;
    }

    .tool-output {
        color: $text-muted;
        margin: 0 0 0 2;
    }

    .todo-block .tool-output {
        color: $text;
    }

    .subagent-parameters {
        margin: 0 0 0 2;
        padding: 0 0 0 1;
        border-left: solid $secondary;
        color: $text-muted;
    }

    .tool-details {
        margin: 1 0 0 0;
        color: $text-muted;
        display: none;
    }

    .subagent-block .tool-details {
        margin: 0 0 0 2;
        padding: 0 0 0 1;
        border-left: solid $accent;
        color: $text;
    }

    .subagent-block.-running .tool-details {
        border-left: solid $accent;
    }

    .subagent-block.-ok .tool-details {
        border-left: solid $success;
    }

    .subagent-block.-failed .tool-details {
        border-left: solid $error;
    }

    .tool-block.-retryable .block-title {
        color: $warning;
    }

    .tool-block.-ok .block-title {
        color: $success;
    }

    .tool-block.-failed .block-title {
        color: $error;
    }

    .todo-block .block-title {
        color: $success;
    }

    .question-block {
        background: $boost;
        padding: 0 1;
    }

    .question-block OptionList {
        height: auto;
        max-height: 8;
        margin-top: 1;
    }

    .question-block TextArea {
        height: 3;
        margin-top: 1;
        border: tall $accent;
    }

    #interaction-sheet {
        height: auto;
        max-height: 16;
        display: none;
        background: $panel;
        border-top: solid $primary;
        padding: 1 2;
    }

    #interaction-sheet .interaction-block {
        height: auto;
        max-height: 14;
        background: transparent;
        padding: 0;
    }

    #interaction-sheet .block-title {
        color: $accent;
        text-style: bold;
    }

    #interaction-sheet OptionList {
        height: auto;
        min-height: 3;
        max-height: 10;
        margin-top: 1;
        color: #e5e7eb !important;
        background: transparent !important;
        border: none !important;
        padding: 0;
    }

    #interaction-sheet OptionList > .option-list--option {
        color: #e5e7eb !important;
        padding: 0 1;
    }

    #interaction-sheet OptionList > .option-list--option-highlighted {
        color: #ffffff !important;
        background: #414868 !important;
        text-style: bold !important;
    }

    #interaction-sheet OptionList:focus > .option-list--option-highlighted {
        color: #ffffff !important;
        background: #7aa2f7 40% !important;
        text-style: bold !important;
    }

    #interaction-sheet OptionList > .option-list--option-disabled {
        color: #7f849c !important;
    }

    #interaction-sheet OptionList > .option-list--option-hover {
        background: #292e42 !important;
    }

    #interaction-sheet .inline-choice-options {
        height: auto;
        min-height: 3;
        max-height: 10;
        margin-top: 1;
        color: #e5e7eb;
        background: transparent;
    }

    #interaction-sheet .screen-help {
        color: $text-muted;
        margin-top: 0;
    }

    Screen.-light-theme #interaction-sheet,
    Screen.-light-theme #prompt-suggestions {
        background: #fdf6e3;
        color: #073642;
    }

    Screen.-light-theme #interaction-sheet .block-title {
        color: #586e75;
    }

    Screen.-light-theme #interaction-sheet OptionList,
    Screen.-light-theme #prompt-suggestions {
        color: #073642 !important;
        background: #fdf6e3 !important;
    }

    Screen.-light-theme #interaction-sheet OptionList > .option-list--option,
    Screen.-light-theme #prompt-suggestions > .option-list--option {
        color: #073642 !important;
    }

    Screen.-light-theme #interaction-sheet OptionList > .option-list--option-highlighted,
    Screen.-light-theme #interaction-sheet OptionList:focus > .option-list--option-highlighted,
    Screen.-light-theme #prompt-suggestions > .option-list--option-highlighted {
        color: #fdf6e3 !important;
        background: #268bd2 !important;
        text-style: bold !important;
    }

    Screen.-light-theme #interaction-sheet OptionList > .option-list--option-disabled,
    Screen.-light-theme #prompt-suggestions > .option-list--option-disabled {
        color: #93a1a1 !important;
    }

    Screen.-light-theme #interaction-sheet OptionList > .option-list--option-hover,
    Screen.-light-theme #prompt-suggestions > .option-list--option-hover {
        background: #eee8d5 !important;
    }

    Screen.-light-theme #interaction-sheet .screen-help,
    Screen.-light-theme #interaction-sheet .inline-choice-options {
        color: #586e75;
    }

    .diff-block {
        background: transparent;
        margin: 0 0 1 0;
    }

    .error-block {
        background: transparent;
    }

    .usage-line {
        height: 1;
        margin: 0;
        padding: 0 1;
        color: $text-muted;
        display: none;
    }
    """
