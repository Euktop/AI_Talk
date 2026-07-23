from pathlib import Path
from ai_talk.domain.interfaces import IFileReader

class LocalFileReader:
    def read(self, source: str) -> str:
        path = Path(source)
        if path.exists() and path.is_file():
            return path.read_text(encoding='utf-8')
        return str(source)
