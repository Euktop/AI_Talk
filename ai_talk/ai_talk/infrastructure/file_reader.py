from pathlib import Path
from ai_talk.domain.interfaces import IFileReader

class LocalFileReader:
    def read(self, source: str) -> str:
        path = Path(source)
        # Если путь похож на файл (есть расширение), но не существует - бросаем ошибку
        if path.suffix.lower() in ['.md', '.txt', '.json', '.csv']:
            if not path.exists():
                raise FileNotFoundError(f"Файл не найден: {path.absolute()}")
            return path.read_text(encoding='utf-8')
        if path.exists() and path.is_file():
            return path.read_text(encoding='utf-8')
        return str(source)
