from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Literal

from deepy.llm.multimodal import (
    ImageAttachmentError,
    PromptImageAttachment,
    UNSUPPORTED_IMAGE_INPUT_MESSAGE,
    build_prompt_image_attachment,
)
from deepy.ui.shared.input.clipboard import ClipboardImage as ClipboardImage
from deepy.ui.shared.input.clipboard import clipboard_image


@dataclass(frozen=True)
class ImagePasteResult:
    handled: bool
    attachment: PromptImageAttachment | None = None
    notice: str = ""


@dataclass(frozen=True)
class ImageLabelEdit:
    text: str
    cursor_position: int


ClipboardImageReader = Callable[[], ClipboardImage | None]


@dataclass
class ImageAttachmentController:
    supports_image_input: bool
    clipboard_reader: ClipboardImageReader = field(default_factory=lambda: clipboard_image)
    attachments: list[PromptImageAttachment] = field(default_factory=list)

    def paste_image_from_clipboard(self) -> ImagePasteResult:
        image = self.clipboard_reader()
        if image is None:
            return ImagePasteResult(handled=False)
        if not self.supports_image_input:
            return ImagePasteResult(handled=True, notice=UNSUPPORTED_IMAGE_INPUT_MESSAGE)
        try:
            attachment = self.attach_image(image.data, image.mime_type)
        except ImageAttachmentError as exc:
            return ImagePasteResult(handled=True, notice=str(exc))
        return ImagePasteResult(handled=True, attachment=attachment)

    def attach_image(self, data: bytes, mime_type: str) -> PromptImageAttachment:
        attachment = build_prompt_image_attachment(
            data=data,
            mime_type=mime_type,
            index=len(self.attachments) + 1,
        )
        self.attachments.append(attachment)
        return attachment

    def collect_and_reset(self) -> list[PromptImageAttachment]:
        attachments = list(self.attachments)
        self.attachments.clear()
        return attachments

    def collect_from_prompt_text(self, text: str) -> tuple[str, list[PromptImageAttachment]]:
        self.sync_to_prompt_text(text)
        attachments = list(self.attachments)
        cleaned_text = remove_image_attachment_labels(text, attachments).strip()
        self.clear()
        return cleaned_text, attachments

    def sync_to_prompt_text(self, text: str) -> bool:
        kept = [attachment for attachment in self.attachments if attachment.display_label in text]
        if len(kept) == len(self.attachments):
            return False
        self.attachments = kept
        return True

    def delete_label_near_cursor(
        self,
        text: str,
        cursor_position: int,
        *,
        direction: Literal["backward", "forward"],
    ) -> ImageLabelEdit | None:
        edit = delete_image_attachment_label_at_cursor(
            text,
            cursor_position,
            self.attachments,
            direction=direction,
        )
        if edit is not None:
            self.sync_to_prompt_text(edit.text)
        return edit

    def clear(self) -> None:
        self.attachments.clear()


def remove_image_attachment_labels(
    text: str,
    attachments: list[PromptImageAttachment],
) -> str:
    cleaned = text
    for attachment in attachments:
        cleaned = cleaned.replace(attachment.display_label, "")
    return cleaned


def image_attachment_input_text(
    attachment: PromptImageAttachment,
    *,
    text_before_cursor: str = "",
    text_after_cursor: str = "",
) -> str:
    prefix = "" if not text_before_cursor or text_before_cursor[-1].isspace() else " "
    suffix = "" if not text_after_cursor or text_after_cursor[0].isspace() else " "
    return f"{prefix}{attachment.display_label}{suffix}"


def delete_image_attachment_label_at_cursor(
    text: str,
    cursor_position: int,
    attachments: list[PromptImageAttachment],
    *,
    direction: Literal["backward", "forward"],
) -> ImageLabelEdit | None:
    cursor = max(0, min(cursor_position, len(text)))
    for attachment in attachments:
        label = attachment.display_label
        start = text.find(label)
        while start != -1:
            end = start + len(label)
            should_delete = (
                start < cursor <= end
                if direction == "backward"
                else start <= cursor < end
            )
            if should_delete:
                return ImageLabelEdit(
                    text=f"{text[:start]}{text[end:]}",
                    cursor_position=start,
                )
            start = text.find(label, start + 1)
    return None
