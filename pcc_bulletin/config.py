import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Config:
    api_key: str
    bulletin_folder: Path
    sermon_notes_root: Path
    model: str = "claude-sonnet-4-6"

    @classmethod
    def from_env(cls) -> "Config":
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. "
                "Edit /home/dan/.config/pcc-bulletin/env and add it."
            )
        bulletin_folder = Path(
            os.environ.get("PCC_BULLETIN_FOLDER", "/home/dan/Documents/PCC Bulletins")
        )
        sermon_notes_root = Path(
            os.environ.get("PCC_SERMON_NOTES_ROOT", "/MaresLeg/Church/SermonNotes")
        )
        model = os.environ.get("PCC_MODEL", "claude-sonnet-4-6")
        return cls(
            api_key=api_key,
            bulletin_folder=bulletin_folder,
            sermon_notes_root=sermon_notes_root,
            model=model,
        )
