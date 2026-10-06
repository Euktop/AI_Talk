"""Pytest-конфигурация для тестов ai_talk.

Проект лежит внутри монорепы D:\repos\AI_Talk. Если pytest запускается
из корня монорепы, Python видит каталог 'ai_talk/' (корень проекта, без
__init__.py) как namespace-пакет и импортирует пустышку вместо реального
пакета 'ai_talk/ai_talk/'.

Этот conftest ставит корень проекта первым в sys.path, чтобы
'import ai_talk' всегда находил настоящий пакет независимо от CWD.
"""
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
