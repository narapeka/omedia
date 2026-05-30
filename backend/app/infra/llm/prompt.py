from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.core.error import ConfigurationError


@dataclass(frozen=True)
class PromptSet:
    media_match_system: str
    media_match_user: str
    media_match_batch_system: str
    media_match_batch_user: str
    tv_resolution_system: str
    tv_resolution_user: str

    @classmethod
    def from_dir(cls, prompt_dir: str | Path | None = None) -> "PromptSet":
        base = Path(prompt_dir) if prompt_dir else Path(__file__).with_name("prompts")
        files = {
            "media_match_system": "media_match_system.txt",
            "media_match_user": "media_match_user.txt",
            "media_match_batch_system": "media_match_batch_system.txt",
            "media_match_batch_user": "media_match_batch_user.txt",
            "tv_resolution_system": "tv_resolution_system.txt",
            "tv_resolution_user": "tv_resolution_user.txt",
        }
        values: dict[str, str] = {}
        missing = []
        for field, filename in files.items():
            path = base / filename
            if not path.exists():
                missing.append(str(path))
                continue
            values[field] = path.read_text(encoding="utf-8").strip()
        if missing:
            raise ConfigurationError(f"Missing LLM prompt file(s): {', '.join(missing)}")

        prompt_set = cls(**values)
        _require_placeholders(prompt_set.media_match_user, "{{INPUT_JSON}}", prompt_name="media_match_user.txt")
        _require_placeholders(
            prompt_set.media_match_batch_user,
            "{{INPUT_JSON}}",
            prompt_name="media_match_batch_user.txt",
        )
        _require_placeholders(
            prompt_set.tv_resolution_user,
            "{{SHOW_NAME}}",
            "{{FILENAMES_JSON}}",
            "{{TMDB_CONTEXT}}",
            prompt_name="tv_resolution_user.txt",
        )
        return prompt_set


def render(template: str, **values: str) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", value)
    return rendered


def _require_placeholders(template: str, *placeholders: str, prompt_name: str) -> None:
    missing = [placeholder for placeholder in placeholders if placeholder not in template]
    if missing:
        raise ConfigurationError(f"{prompt_name} is missing placeholder(s): {', '.join(missing)}")
