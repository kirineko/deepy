from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

from prompt_toolkit.completion import CompleteEvent
from prompt_toolkit.document import Document
from prompt_toolkit.keys import Keys

from deepy.llm.multimodal import UNSUPPORTED_IMAGE_INPUT_MESSAGE
from deepy.skills import SkillInfo
from deepy.ui.shared.input.file_mentions import FileMentionCompleter
from deepy.ui.shared.input.file_mentions import FileMentionDiscovery
from deepy.ui.shared.input.file_mentions import extract_file_mention_fragment
from deepy.ui.shared.input.file_mentions import is_ignored_file_mention_name
from deepy.ui.shared.input.file_mentions import rank_file_mention_candidates
from deepy.ui.shared.input import clipboard
from deepy.ui.shared.input import image_input
from deepy.ui.classic.prompt.prompt_input import CTRL_D_EXIT_CONFIRM_SIGNAL
from deepy.ui.classic.prompt.prompt_input import PROMPT_MESSAGE
from deepy.ui.classic.prompt.prompt_input import PROMPT_PLACEHOLDER
from deepy.ui.classic.prompt.prompt_input import PROMPT_TOOLBAR
from deepy.ui.classic.prompt.prompt_input import PROMPT_TOOLBAR_BACKGROUND
from deepy.ui.classic.prompt.prompt_input import PROMPT_TOOLBAR_FOREGROUND
from deepy.input_suggestions import InputSuggestionController
from deepy.ui.classic.prompt.prompt_input import InputSuggestionAutoSuggest
from deepy.ui.classic.prompt.prompt_input import add_unique_skill
from deepy.ui.classic.prompt.prompt_input import build_prompt_key_bindings
from deepy.ui.classic.prompt.prompt_input import build_prompt_toolbar
from deepy.ui.classic.prompt.prompt_input import character_width
from deepy.ui.classic.prompt.prompt_input import create_prompt_session
from deepy.ui.classic.prompt.prompt_input import format_selected_skills_status
from deepy.ui.classic.prompt.prompt_input import input_suggestion_placeholder
from deepy.ui.classic.prompt.prompt_input import is_skill_selected
from deepy.ui.classic.prompt.prompt_input import measure_text_position
from deepy.ui.classic.prompt.prompt_input import prompt_toolbar
from deepy.ui.classic.prompt.prompt_input import prompt_for_input
from deepy.ui.classic.prompt.prompt_input import prompt_style
from deepy.ui.classic.prompt.prompt_input import text_width
from deepy.ui.classic.prompt.prompt_input import toggle_skill_selection
from deepy.ui.shared.input.image_input import ClipboardImage, ImageAttachmentController
from deepy.ui.shared.input.slash_commands import SlashCommandItem
from deepy.ui.classic.status.status_footer import StatusFooter, StatusFooterSegment


def _toolbar_text(toolbar: object) -> str:
    return "".join(text for _style, text in toolbar) if isinstance(toolbar, list) else str(toolbar)


def _skill(name: str, description: str) -> SkillInfo:
    return SkillInfo(name=name, path=Path(f"/skills/{name}/SKILL.md"), description=description)


def _completion_texts(completer, text: str) -> list[str]:
    document = Document(text=text, cursor_position=len(text))
    event = CompleteEvent(completion_requested=True)
    return [completion.text for completion in completer.get_completions(document, event)]


def _completions(completer, text: str):
    document = Document(text=text, cursor_position=len(text))
    event = CompleteEvent(completion_requested=True)
    return list(completer.get_completions(document, event))


def _key_values(binding) -> tuple[str, ...]:
    return tuple(getattr(key, "value", str(key)) for key in binding.keys)


def test_extract_file_mention_fragment_handles_plain_scoped_and_invalid_tokens():
    assert extract_file_mention_fragment("@").fragment == ""
    assert extract_file_mention_fragment("please inspect @src/deepy").fragment == "src/deepy"
    assert extract_file_mention_fragment("email@example.com") is None
    assert extract_file_mention_fragment("look @src then continue") is None
    assert extract_file_mention_fragment("literal@@src") is None


def test_file_mention_top_level_discovery_filters_ignored_and_formats_dirs(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "README.md").write_text("# readme")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / ".git").mkdir()
    (tmp_path / "draft file.txt").write_text("")

    paths = FileMentionDiscovery(tmp_path).top_level_paths()

    assert "src/" in paths
    assert "README.md" in paths
    assert "node_modules/" not in paths
    assert ".git/" not in paths
    assert "draft file.txt" not in paths
    assert is_ignored_file_mention_name("node_modules")


def test_image_attachment_controller_attaches_supported_clipboard_image():
    controller = ImageAttachmentController(
        supports_image_input=True,
        clipboard_reader=lambda: ClipboardImage(data=b"image", mime_type="image/png"),
    )

    assert controller.paste_image_from_clipboard().handled
    attachments = controller.collect_and_reset()
    assert attachments[0].data_url == "data:image/png;base64,aW1hZ2U="


def test_image_attachment_controller_collects_only_labels_still_in_prompt_text():
    controller = ImageAttachmentController(supports_image_input=True)
    first = controller.attach_image(b"one", "image/png")
    second = controller.attach_image(b"two", "image/png")

    text, attachments = controller.collect_from_prompt_text(f"inspect {first.display_label}")

    assert text == "inspect"
    assert attachments == [first]
    assert second not in attachments
    assert controller.attachments == []


def test_image_attachment_controller_syncs_deleted_prompt_label():
    controller = ImageAttachmentController(supports_image_input=True)
    first = controller.attach_image(b"one", "image/png")
    second = controller.attach_image(b"two", "image/png")

    assert controller.sync_to_prompt_text(f"keep {second.display_label}")

    assert controller.attachments == [second]
    assert first not in controller.attachments


def test_image_attachment_controller_deletes_label_as_atomic_unit():
    controller = ImageAttachmentController(supports_image_input=True)
    attachment = controller.attach_image(b"image", "image/png")
    text = f"inspect {attachment.display_label} now"
    cursor = text.index(attachment.display_label) + len(attachment.display_label)

    edit = controller.delete_label_near_cursor(text, cursor, direction="backward")

    assert edit is not None
    assert edit.text == "inspect  now"
    assert edit.cursor_position == len("inspect ")
    assert controller.attachments == []


def test_image_attachment_controller_rejects_unsupported_model_without_clearing_text_state():
    controller = ImageAttachmentController(
        supports_image_input=False,
        clipboard_reader=lambda: ClipboardImage(data=b"image", mime_type="image/png"),
    )

    result = controller.paste_image_from_clipboard()
    assert result.handled
    assert "不支持图片输入" in result.notice
    assert controller.attachments == []


def test_ctrl_v_unsupported_image_notice_renders_through_terminal_runner(monkeypatch):
    controller = ImageAttachmentController(
        supports_image_input=False,
        clipboard_reader=lambda: ClipboardImage(data=b"image", mime_type="image/png"),
    )
    notices: list[str] = []
    terminal_callbacks = []
    invalidated: list[bool] = []

    def fake_run_in_terminal(callback):
        terminal_callbacks.append(callback)
        callback()

    monkeypatch.setattr("deepy.ui.classic.prompt.prompt_input.run_in_terminal", fake_run_in_terminal)
    bindings = build_prompt_key_bindings(
        image_attachments=controller,
        on_image_paste_notice=notices.append,
    )
    control_v = next(binding for binding in bindings.bindings if binding.keys == (Keys.ControlV,))
    buffer = SimpleNamespace(
        document=Document("typed", cursor_position=5),
        insert_text=lambda _text: None,
    )
    event = SimpleNamespace(
        current_buffer=buffer,
        app=SimpleNamespace(
            clipboard=SimpleNamespace(get_data=lambda: (_ for _ in ()).throw(AssertionError)),
            invalidate=lambda: invalidated.append(True),
        ),
    )

    control_v.handler(event)

    assert terminal_callbacks
    assert notices == [UNSUPPORTED_IMAGE_INPUT_MESSAGE]
    assert invalidated == [True]


def test_ctrl_backspace_deletes_image_label_as_atomic_unit(monkeypatch):
    controller = ImageAttachmentController(supports_image_input=True)
    attachment = controller.attach_image(b"image", "image/png")
    text = f"inspect {attachment.display_label}"
    invalidated: list[bool] = []
    calls: list[str] = []
    bindings = build_prompt_key_bindings(image_attachments=controller)
    backspace = next(
        binding for binding in bindings.bindings if _key_values(binding) in {("backspace",), ("c-h",)}
    )
    buffer = SimpleNamespace(
        text=text,
        cursor_position=len(text),
        delete_before_cursor=lambda count=1: calls.append(f"delete-before:{count}"),
    )
    event = SimpleNamespace(
        current_buffer=buffer,
        app=SimpleNamespace(invalidate=lambda: invalidated.append(True)),
    )

    backspace.handler(event)

    assert buffer.text == "inspect "
    assert buffer.cursor_position == len("inspect ")
    assert controller.attachments == []
    assert invalidated == [True]
    assert calls == []


def test_delete_deletes_image_label_as_atomic_unit():
    controller = ImageAttachmentController(supports_image_input=True)
    attachment = controller.attach_image(b"image", "image/png")
    text = f"inspect {attachment.display_label} now"
    invalidated: list[bool] = []
    calls: list[str] = []
    bindings = build_prompt_key_bindings(image_attachments=controller)
    delete = next(binding for binding in bindings.bindings if _key_values(binding) == ("delete",))
    buffer = SimpleNamespace(
        text=text,
        cursor_position=text.index(attachment.display_label),
        delete=lambda count=1: calls.append(f"delete:{count}"),
    )
    event = SimpleNamespace(
        current_buffer=buffer,
        app=SimpleNamespace(invalidate=lambda: invalidated.append(True)),
    )

    delete.handler(event)

    assert buffer.text == "inspect  now"
    assert buffer.cursor_position == len("inspect ")
    assert controller.attachments == []
    assert invalidated == [True]
    assert calls == []


def test_image_attachment_controller_ignores_non_image_clipboard():
    controller = ImageAttachmentController(
        supports_image_input=True,
        clipboard_reader=lambda: None,
    )

    assert not controller.paste_image_from_clipboard().handled


def test_clipboard_image_reads_macos_copied_image_file(tmp_path, monkeypatch):
    png_data = b"\x89PNG\r\n\x1a\nimage"
    path = tmp_path / "screen.png"
    path.write_bytes(png_data)

    monkeypatch.setattr(clipboard.platform, "system", lambda: "Darwin")

    def fake_run(args, **kwargs):
        script = " ".join(str(arg) for arg in args)
        if "POSIX path" in script:
            return subprocess.CompletedProcess(args, 0, stdout=f"{path}\n", stderr="")
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(clipboard.subprocess, "run", fake_run)

    image = image_input.clipboard_image()

    assert image == ClipboardImage(data=png_data, mime_type="image/png")


def test_clipboard_image_reads_macos_raw_png(monkeypatch):
    png_data = b"\x89PNG\r\n\x1a\nraw"

    monkeypatch.setattr(clipboard.platform, "system", lambda: "Darwin")

    def fake_run(args, **kwargs):
        script = " ".join(str(arg) for arg in args)
        if "POSIX path" in script:
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        if "PNGf" in script:
            return subprocess.CompletedProcess(
                args,
                0,
                stdout=f"«data PNGf{png_data.hex().upper()}»\n",
                stderr="",
            )
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(clipboard.subprocess, "run", fake_run)

    image = image_input.clipboard_image()

    assert image == ClipboardImage(data=png_data, mime_type="image/png")


def test_clipboard_image_reads_linux_uri_list_image_file(tmp_path, monkeypatch):
    jpeg_data = b"\xff\xd8\xffimage"
    path = tmp_path / "copied.jpg"
    path.write_bytes(jpeg_data)

    monkeypatch.setattr(clipboard.platform, "system", lambda: "Linux")
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    monkeypatch.setattr(clipboard.shutil, "which", lambda name: f"/usr/bin/{name}")

    def fake_run(args, **kwargs):
        if "text/uri-list" in args:
            return subprocess.CompletedProcess(
                args,
                0,
                stdout=f"file://{path}\n".encode(),
                stderr=b"",
            )
        return subprocess.CompletedProcess(args, 1, stdout=b"", stderr=b"")

    monkeypatch.setattr(clipboard.subprocess, "run", fake_run)

    image = image_input.clipboard_image()

    assert image == ClipboardImage(data=jpeg_data, mime_type="image/jpeg")


def test_clipboard_image_reads_linux_raw_webp(monkeypatch):
    webp_data = b"RIFF\x10\x00\x00\x00WEBPVP8 "

    monkeypatch.setattr(clipboard.platform, "system", lambda: "Linux")
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.setattr(clipboard.shutil, "which", lambda name: f"/usr/bin/{name}")

    def fake_run(args, **kwargs):
        if "image/webp" in args:
            return subprocess.CompletedProcess(args, 0, stdout=webp_data, stderr=b"")
        return subprocess.CompletedProcess(args, 1, stdout=b"", stderr=b"")

    monkeypatch.setattr(clipboard.subprocess, "run", fake_run)

    image = image_input.clipboard_image()

    assert image == ClipboardImage(data=webp_data, mime_type="image/webp")


def test_clipboard_image_reads_windows_file_drop(tmp_path, monkeypatch):
    gif_data = b"GIF89aimage"
    path = tmp_path / "copied.gif"
    path.write_bytes(gif_data)

    monkeypatch.setattr(clipboard.platform, "system", lambda: "Windows")
    monkeypatch.setattr(clipboard.shutil, "which", lambda name: "powershell.exe")

    def fake_run(args, **kwargs):
        script = " ".join(str(arg) for arg in args)
        if "GetFileDropList" in script:
            return subprocess.CompletedProcess(args, 0, stdout=f"{path}\n", stderr="")
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(clipboard.subprocess, "run", fake_run)

    image = image_input.clipboard_image()

    assert image == ClipboardImage(data=gif_data, mime_type="image/gif")


def test_clipboard_image_reads_windows_raw_image_as_png(monkeypatch):
    png_data = b"\x89PNG\r\n\x1a\nwindows"

    monkeypatch.setattr(clipboard.platform, "system", lambda: "Windows")
    monkeypatch.setattr(clipboard.shutil, "which", lambda name: "powershell.exe")

    def fake_run(args, **kwargs):
        script = " ".join(str(arg) for arg in args)
        if "GetFileDropList" in script:
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        if "ContainsImage" in script:
            output_path = Path(args[-1])
            output_path.write_bytes(png_data)
            return subprocess.CompletedProcess(args, 0, stdout=f"{output_path}\n", stderr="")
        return subprocess.CompletedProcess(args, 1, stdout="", stderr="")

    monkeypatch.setattr(clipboard.subprocess, "run", fake_run)

    image = image_input.clipboard_image()

    assert image == ClipboardImage(data=png_data, mime_type="image/png")


def test_file_mention_scoped_discovery_descends_under_typed_directory(tmp_path):
    (tmp_path / "src" / "deepy").mkdir(parents=True)
    (tmp_path / "src" / "deepy" / "cli.py").write_text("")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "cli.py").write_text("")

    paths = FileMentionDiscovery(tmp_path).deep_paths("src")

    assert "src/" in paths
    assert "src/deepy/" in paths
    assert "src/deepy/cli.py" in paths
    assert "docs/cli.py" not in paths


def test_file_mention_scoped_discovery_rejects_project_root_escape(tmp_path):
    outside = tmp_path.parent / f"{tmp_path.name}-outside-file.txt"
    outside.write_text("")
    try:
        assert FileMentionDiscovery(tmp_path).deep_paths("..") == []
        assert FileMentionDiscovery(tmp_path).deep_paths("../") == []
    finally:
        outside.unlink(missing_ok=True)


def test_file_mention_ranking_prefers_basename_matches():
    paths = [
        "src/features/cache.py",
        "src/web/prefetch.py",
        "src/web/fetch.py",
    ]

    assert rank_file_mention_candidates(paths, "fetch") == [
        "src/web/fetch.py",
        "src/web/prefetch.py",
        "src/features/cache.py",
    ]


def test_file_mention_completer_short_fragment_matches_nested_paths(tmp_path):
    (tmp_path / "src" / "deepy").mkdir(parents=True)
    (tmp_path / "src" / "deepy" / "audit.py").write_text("")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "architecture.md").write_text("")

    completer = FileMentionCompleter(tmp_path)

    texts = _completion_texts(completer, "inspect @a")

    assert "src/deepy/audit.py" in texts
    assert "docs/architecture.md" in texts


def test_file_mention_completer_bare_at_stays_top_level(tmp_path):
    (tmp_path / "src" / "deepy").mkdir(parents=True)
    (tmp_path / "src" / "deepy" / "audit.py").write_text("")
    (tmp_path / "README.md").write_text("")

    completer = FileMentionCompleter(tmp_path)

    texts = _completion_texts(completer, "inspect @")

    assert "src/" in texts
    assert "README.md" in texts
    assert "src/deepy/" not in texts
    assert "src/deepy/audit.py" not in texts


def test_file_mention_completer_short_fragment_keeps_ignored_paths_filtered(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "alpha.py").write_text("")
    (tmp_path / "node_modules" / "alpha").mkdir(parents=True)
    (tmp_path / "node_modules" / "alpha" / "index.js").write_text("")
    (tmp_path / ".git" / "alpha").mkdir(parents=True)
    (tmp_path / ".git" / "alpha" / "HEAD").write_text("")

    completer = FileMentionCompleter(tmp_path)

    texts = _completion_texts(completer, "inspect @a")

    assert "src/alpha.py" in texts
    assert all("node_modules" not in text for text in texts)
    assert all(".git" not in text for text in texts)


def test_file_mention_completer_short_fragment_prefers_basename_prefix(tmp_path):
    (tmp_path / "src" / "web").mkdir(parents=True)
    (tmp_path / "src" / "web" / "fetch.py").write_text("")
    (tmp_path / "src" / "web" / "prefetch.py").write_text("")
    (tmp_path / "src" / "features").mkdir(parents=True)
    (tmp_path / "src" / "features" / "cache.py").write_text("")

    completer = FileMentionCompleter(tmp_path)

    texts = _completion_texts(completer, "inspect @f")

    assert texts.index("src/web/fetch.py") < texts.index("src/web/prefetch.py")
    assert texts.index("src/web/fetch.py") < texts.index("src/features/cache.py")


def test_file_mention_discovery_uses_short_lived_cache(tmp_path):
    (tmp_path / "README.md").write_text("")
    discovery = FileMentionDiscovery(tmp_path, refresh_interval=999)

    assert "README.md" in discovery.top_level_paths()
    (tmp_path / "later.py").write_text("")

    assert "later.py" not in discovery.top_level_paths()


def test_file_mention_completer_short_circuits_existing_file(tmp_path):
    (tmp_path / "AGENTS.md").write_text("")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "AGENTS.md").write_text("")

    completer = FileMentionCompleter(tmp_path)

    assert _completion_texts(completer, "@AGENTS.md") == []


def test_file_mention_completer_replaces_only_current_fragment(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "deepy.py").write_text("")

    completer = FileMentionCompleter(tmp_path)

    completions = _completions(completer, "inspect @src/de")
    selected = next(completion for completion in completions if completion.text == "src/deepy.py")

    assert selected.start_position == -len("src/de")


def test_create_prompt_session_combines_slash_and_file_mention_completion(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "deepy.py").write_text("")
    session = create_prompt_session(
        slash_commands=[
            SlashCommandItem("new", "new", "/new", "Start fresh"),
            SlashCommandItem("resume", "resume", "/resume", "Resume"),
        ],
        history_path=tmp_path / "history.txt",
        project_root=tmp_path,
    )

    assert session.completer is not None
    assert "/new" in _completion_texts(session.completer, "/")
    assert "src/" in _completion_texts(session.completer, "see @")


def test_create_prompt_session_slash_completions_include_metadata_and_ranking(tmp_path):
    (tmp_path / "src").mkdir()
    session = create_prompt_session(
        slash_commands=[
            SlashCommandItem("reset", "reset", "/reset", "Reset config"),
            SlashCommandItem("resume", "resume", "/resume", "Resume session"),
            SlashCommandItem("subagent", "reviewer", "/reviewer", "Review the current change"),
            SlashCommandItem(
                "skill",
                "fresh",
                "/fresh",
                "Fresh skill",
                SkillInfo("fresh", Path("/skills/fresh"), "Fresh skill"),
            ),
            SlashCommandItem(
                "skill",
                "loaded",
                "/loaded",
                "Loaded skill",
                SkillInfo("loaded", Path("/skills/loaded"), "Loaded skill", is_loaded=True),
            ),
        ],
        history_path=tmp_path / "history.txt",
        project_root=tmp_path,
    )

    completions = _completions(session.completer, "/")
    texts = [completion.text for completion in completions]
    assert texts[:2] == ["/resume", "/reviewer"]
    assert texts.index("/loaded") < texts.index("/fresh")
    loaded = next(completion for completion in completions if completion.text == "/loaded")
    assert loaded.display_text == "/loaded *"
    assert loaded.display_meta_text == "Loaded skill"
    legacy = _completions(session.completer, "/skill:")[0]
    assert legacy.text == "/skill:loaded"
    assert legacy.display_text == "/skill:loaded *"

    assert "src/" not in texts
    assert all(not text.startswith("/") for text in _completion_texts(session.completer, "see @"))


def test_create_prompt_session_suppresses_completion_menu_when_input_suggestion_visible(tmp_path):
    controller = InputSuggestionController()
    controller.set_suggestion("run tests")
    session = create_prompt_session(
        slash_commands=[
            SlashCommandItem("new", "new", "/new", "Start fresh"),
            SlashCommandItem("resume", "resume", "/resume", "Resume"),
        ],
        history_path=tmp_path / "history.txt",
        input_suggestions=controller,
        project_root=tmp_path,
    )

    assert session.completer is not None
    assert _completion_texts(session.completer, "") == []
    assert "/new" in _completion_texts(session.completer, "/")


def test_selected_skill_helpers_format_dedupe_toggle_and_clear_slash_tokens():
    skill = _skill("skill-writer", "Write skills")
    other = _skill("code-review", "Review code")

    assert format_selected_skills_status([]) == ""
    assert format_selected_skills_status([skill, other]) == "⚡ skill-writer, code-review"
    assert is_skill_selected([skill], skill)
    assert add_unique_skill([skill], skill) == [skill]
    assert add_unique_skill([skill], other) == [skill, other]
    assert toggle_skill_selection([skill], skill) == []
    assert toggle_skill_selection([skill], other) == [skill, other]


def test_create_prompt_session_configures_history_multiline_and_slash_completion(tmp_path):
    session = create_prompt_session(
        slash_commands=[
            SlashCommandItem("new", "new", "/new", "Start fresh"),
            SlashCommandItem("resume", "resume", "/resume", "Resume"),
        ],
        history_path=tmp_path / "history.txt",
    )

    assert session.multiline is True
    assert session.completer is not None
    assert (tmp_path / "history.txt").exists()


def test_input_suggestion_auto_suggest_only_renders_for_empty_buffer():
    controller = InputSuggestionController()
    controller.set_suggestion("run tests")
    auto_suggest = InputSuggestionAutoSuggest(controller)

    assert auto_suggest.get_suggestion(None, Document("")).text == "run tests"
    assert auto_suggest.get_suggestion(None, Document("typed")) is None
    assert controller.state.visible is False
    assert controller.state.text == "run tests"
    assert auto_suggest.get_suggestion(None, Document("")).text == "run tests"

    controller.set_suggestion("run tests")
    controller.dismiss()

    assert auto_suggest.get_suggestion(None, Document("")) is None


def test_input_suggestion_completer_stays_suppressed_after_type_delete_cycle(tmp_path):
    controller = InputSuggestionController()
    controller.set_suggestion("run tests")
    session = create_prompt_session(
        slash_commands=[
            SlashCommandItem("new", "new", "/new", "Start fresh"),
            SlashCommandItem("resume", "resume", "/resume", "Resume"),
        ],
        history_path=tmp_path / "history.txt",
        input_suggestions=controller,
        project_root=tmp_path,
    )
    auto_suggest = InputSuggestionAutoSuggest(controller)

    assert session.completer is not None
    assert auto_suggest.get_suggestion(None, Document("typed")) is None
    assert controller.state.text == "run tests"
    assert _completion_texts(session.completer, "") == []
    assert auto_suggest.get_suggestion(None, Document("")).text == "run tests"


def test_prompt_key_bindings_tab_and_right_accept_input_suggestion():
    controller = InputSuggestionController()
    bindings = build_prompt_key_bindings(input_suggestions=controller)
    calls: list[str] = []

    class Buffer:
        complete_state = None
        text = ""

        def insert_text(self, text: str):
            calls.append(text)
            self.text += text

        def start_completion(self, select_first=False):
            calls.append(f"complete:{select_first}")

        def cursor_right(self):
            calls.append("right")

    class Event:
        def __init__(self):
            self.current_buffer = Buffer()

    def key_values(binding):
        return tuple(getattr(key, "value", str(key)) for key in binding.keys)

    tab = next(
        binding for binding in bindings.bindings if key_values(binding) in {("tab",), ("c-i",)}
    )
    right = next(binding for binding in bindings.bindings if key_values(binding) == ("right",))

    controller.set_suggestion("run tests")
    event = Event()
    tab.handler(event)

    assert calls == ["run tests"]
    assert event.current_buffer.text == "run tests"
    assert controller.state.text == "run tests"
    assert controller.state.visible is False

    event = Event()
    controller.set_suggestion("commit changes")
    right.handler(event)

    assert calls == ["run tests", "commit changes"]
    assert event.current_buffer.text == "commit changes"


def test_prompt_key_bindings_tab_accepts_input_suggestion_before_completion():
    controller = InputSuggestionController()
    bindings = build_prompt_key_bindings(input_suggestions=controller)
    calls: list[str] = []

    class CompletionState:
        current_completion = "/new"
        completions = ["/new"]

    class Buffer:
        complete_state = CompletionState()
        text = ""

        def insert_text(self, text: str):
            calls.append(f"insert:{text}")
            self.text += text

        def apply_completion(self, completion):
            calls.append(f"apply:{completion}")

    class Event:
        current_buffer = Buffer()

    def key_values(binding):
        return tuple(getattr(key, "value", str(key)) for key in binding.keys)

    tab = next(
        binding for binding in bindings.bindings if key_values(binding) in {("tab",), ("c-i",)}
    )

    controller.set_suggestion("run tests")
    tab.handler(Event())

    assert calls == ["insert:run tests"]
    assert controller.state.text == "run tests"
    assert controller.state.visible is False


def test_prompt_key_bindings_enter_dismisses_input_suggestion_without_accepting():
    controller = InputSuggestionController()
    bindings = build_prompt_key_bindings(input_suggestions=controller)
    calls: list[str] = []

    class Buffer:
        complete_state = None
        text = ""

        def insert_text(self, text: str):
            calls.append(text)

        def validate_and_handle(self):
            calls.append("submit")

    class Event:
        current_buffer = Buffer()

    def key_values(binding):
        return tuple(getattr(key, "value", str(key)) for key in binding.keys)

    enter = next(binding for binding in bindings.bindings if key_values(binding) == ("c-m",))

    controller.set_suggestion("run tests")
    enter.handler(Event())

    assert calls == ["submit"]
    assert controller.state.text is None


def test_prompt_for_input_uses_styled_prompt_placeholder_and_toolbar():
    class FakePromptSession:
        kwargs = {}

        def prompt(self, message, **kwargs):
            self.message = message
            self.kwargs = kwargs
            return " hello "

    session = FakePromptSession()

    assert prompt_for_input(session) == "hello"
    assert session.message == PROMPT_MESSAGE
    assert session.kwargs["placeholder"] == PROMPT_PLACEHOLDER
    assert session.kwargs["bottom_toolbar"] == PROMPT_TOOLBAR
    assert PROMPT_TOOLBAR_BACKGROUND == "#161821"
    assert PROMPT_TOOLBAR_FOREGROUND == "#a6adc8"


def test_prompt_for_input_uses_input_suggestion_as_empty_prompt_placeholder():
    class FakePromptSession:
        kwargs = {}

        def prompt(self, message, **kwargs):
            self.kwargs = kwargs
            return ""

    controller = InputSuggestionController()
    controller.set_suggestion("run tests")
    session = FakePromptSession()

    assert prompt_for_input(session, input_suggestions=controller) == ""
    assert session.kwargs["placeholder"] == [("class:auto-suggestion", "run tests")]
    assert input_suggestion_placeholder(None) == PROMPT_PLACEHOLDER


def test_prompt_toolbar_uses_cross_platform_newline_help():
    assert prompt_toolbar() == PROMPT_TOOLBAR
    assert PROMPT_TOOLBAR == [("class:toolbar.help", "newline: ctrl+j")]
    assert "ctrl+j" in str(PROMPT_TOOLBAR)
    assert "Ctrl+D" not in str(PROMPT_TOOLBAR)
    assert "Ctrl+Enter" not in str(PROMPT_TOOLBAR)
    assert "Shift+Enter" not in str(PROMPT_TOOLBAR)


def test_build_prompt_toolbar_renders_structured_status_without_exit_help():
    status = StatusFooter(
        (
            StatusFooterSegment("model deepseek-v4-pro[max]", "identity"),
            StatusFooterSegment("cwd ~/repo", "metadata"),
            StatusFooterSegment("ctx 100/1K (10.0%, 900 left)", "context"),
        )
    )
    toolbar = build_prompt_toolbar(status)

    assert isinstance(toolbar, list)
    assert toolbar == [
        ("class:toolbar.title", "model"),
        ("class:toolbar.metadata", " deepseek-v4-pro[max]"),
        ("class:toolbar.separator", " · "),
        ("class:toolbar.title", "cwd"),
        ("class:toolbar.metadata", " ~/repo"),
        ("class:toolbar.separator", " · "),
        ("class:toolbar.title", "ctx"),
        ("class:toolbar.context", " 100/1K (10.0%, 900 left)"),
        ("class:toolbar.separator", " · "),
        ("class:toolbar.title", "newline"),
        ("class:toolbar.metadata", ": ctrl+j"),
    ]
    assert "newline: ctrl+j" in _toolbar_text(toolbar)
    assert "Ctrl+D twice exit" not in str(toolbar)
    assert "Ctrl+Enter" not in str(toolbar)
    assert "Shift+Enter" not in str(toolbar)


def test_prompt_toolbar_style_disables_reverse_background():
    rules = dict(prompt_style().style_rules)

    assert rules["auto-suggestion"] == "dim"
    assert rules["bottom-toolbar"].startswith("noreverse bg:#161821")
    assert rules["toolbar.title"].startswith("noreverse bg:#161821")
    assert rules["toolbar.separator"].startswith("noreverse bg:#161821")


def test_build_prompt_key_bindings_registers_escape_interrupt():
    bindings = build_prompt_key_bindings(on_interrupt=lambda: None)

    assert any("escape" in binding.keys for binding in bindings.bindings)


def test_prompt_key_bindings_enter_submits_and_ctrl_j_inserts_newline():
    bindings = build_prompt_key_bindings()
    calls: list[str] = []

    class Buffer:
        complete_state = None

        def validate_and_handle(self):
            calls.append("submit")

        def insert_text(self, text: str):
            calls.append(text)

    class Event:
        current_buffer = Buffer()

    def key_values(binding):
        return tuple(getattr(key, "value", str(key)) for key in binding.keys)

    enter = next(binding for binding in bindings.bindings if key_values(binding) == ("c-m",))
    ctrl_j = next(binding for binding in bindings.bindings if key_values(binding) == ("c-j",))

    enter.handler(Event())
    ctrl_j.handler(Event())

    assert calls == ["submit", "\n"]


def test_prompt_key_bindings_enter_accepts_completion_without_submitting():
    bindings = build_prompt_key_bindings()
    calls: list[str] = []

    class CompletionState:
        current_completion = "src/main.py"
        completions = ["src/main.py", "README.md"]

    class Buffer:
        complete_state = CompletionState()

        def apply_completion(self, completion):
            calls.append(f"apply:{completion}")

        def cancel_completion(self):
            calls.append("cancel")

        def validate_and_handle(self):
            calls.append("submit")

    class Event:
        current_buffer = Buffer()

    def key_values(binding):
        return tuple(getattr(key, "value", str(key)) for key in binding.keys)

    enter = next(binding for binding in bindings.bindings if key_values(binding) == ("c-m",))

    enter.handler(Event())

    assert calls == ["apply:src/main.py"]


def test_prompt_key_bindings_enter_cancels_empty_completion_state_without_submitting():
    bindings = build_prompt_key_bindings()
    calls: list[str] = []

    class CompletionState:
        current_completion = None
        completions = []

    class Buffer:
        complete_state = CompletionState()

        def apply_completion(self, completion):
            calls.append(f"apply:{completion}")

        def cancel_completion(self):
            calls.append("cancel")

        def validate_and_handle(self):
            calls.append("submit")

    class Event:
        current_buffer = Buffer()

    def key_values(binding):
        return tuple(getattr(key, "value", str(key)) for key in binding.keys)

    enter = next(binding for binding in bindings.bindings if key_values(binding) == ("c-m",))

    enter.handler(Event())

    assert calls == ["cancel"]


def test_prompt_key_bindings_do_not_register_shift_or_ctrl_enter_sequences():
    bindings = build_prompt_key_bindings()

    def key_values(binding):
        return tuple(getattr(key, "value", str(key)) for key in binding.keys)

    assert any(key_values(binding) == ("c-j",) for binding in bindings.bindings)
    assert not any(key_values(binding) == ("escape", "c-m") for binding in bindings.bindings)


def test_prompt_key_bindings_shift_tab_cycles_audit_mode():
    calls: list[str] = []
    bindings = build_prompt_key_bindings(on_audit_mode_cycle=lambda: calls.append("cycle"))

    def key_values(binding):
        return tuple(getattr(key, "value", str(key)) for key in binding.keys)

    shift_tab = next(binding for binding in bindings.bindings if key_values(binding) == ("s-tab",))
    shift_tab.handler(object())

    assert calls == ["cycle"]


def test_prompt_key_bindings_ctrl_d_returns_exit_confirmation_when_empty():
    bindings = build_prompt_key_bindings()
    results: list[str] = []

    class Buffer:
        text = ""

        def delete(self):
            results.append("delete")

    class App:
        def exit(self, *, result):
            results.append(result)

    class Event:
        current_buffer = Buffer()
        app = App()

    def key_values(binding):
        return tuple(getattr(key, "value", str(key)) for key in binding.keys)

    ctrl_d = next(binding for binding in bindings.bindings if key_values(binding) == ("c-d",))

    ctrl_d.handler(Event())

    assert results == [CTRL_D_EXIT_CONFIRM_SIGNAL]


def test_prompt_key_bindings_ctrl_d_deletes_when_buffer_has_text():
    bindings = build_prompt_key_bindings()
    calls: list[str] = []

    class Buffer:
        text = "hello"

        def delete(self):
            calls.append("delete")

    class App:
        def exit(self, *, result):
            calls.append(result)

    class Event:
        current_buffer = Buffer()
        app = App()

    def key_values(binding):
        return tuple(getattr(key, "value", str(key)) for key in binding.keys)

    ctrl_d = next(binding for binding in bindings.bindings if key_values(binding) == ("c-d",))

    ctrl_d.handler(Event())

    assert calls == ["delete"]


def test_text_width_counts_cjk_and_control_characters():
    assert text_width("hello") == 5
    assert text_width("你好") == 4
    assert character_width("\n") == 0
    assert measure_text_position("ab", width=80, initial_column=2).column == 4
