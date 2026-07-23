import time
import uuid
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
from ai_talk.domain.interfaces import ILLMClient, Message
from ai_talk.domain.exceptions import AITalkGenerationError

class CustomFileClient:
    def __init__(self, custom_dir: str = "запросы_к_ии"):
        self.custom_dir = Path(custom_dir)
        self.custom_dir.mkdir(parents=True, exist_ok=True)

    def chat(self, messages: List[Message], temperature: float = 0.7) -> str:
        system_prompt = ""
        user_message = ""
        for m in messages:
            if m.role == "system":
                system_prompt = m.content
            elif m.role == "user":
                user_message = m.content

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        short_id = str(uuid.uuid4())[:8]
        filename = f"{timestamp}_{short_id}.md"
        filepath = self.custom_dir / filename

        content = (
            f"# Запрос к ИИ\n"
            f"## Системный промпт\n"
            f"{system_prompt if system_prompt else 'Не указан'}\n"
            f"## Вопрос\n"
            f"{user_message}\n"
            f"## Ответ\n"
            f"<!-- Напишите ваш ответ ниже этой строки, затем сохраните файл -->\n"
        )
        filepath.write_text(content, encoding='utf-8')
        print(f"📝 Файл запроса создан: {filepath.absolute()}")
        print(f"⏳ Ожидание ответа... Откройте файл и напишите ответ в секции '## Ответ'")

        timeout = 3600
        poll_interval = 5
        elapsed = 0
        while elapsed < timeout:
            time.sleep(poll_interval)
            elapsed += poll_interval
            current_content = filepath.read_text(encoding='utf-8')
            answer = self._extract_answer(current_content)
            if answer:
                print(f"✅ Ответ получен! ({elapsed} сек)")
                done_dir = self.custom_dir / "архив"
                done_dir.mkdir(exist_ok=True)
                filepath.rename(done_dir / f"done_{filename}")
                return answer
            if elapsed % 30 == 0:
                print(f"⏳ Ожидание... ({elapsed} сек)")

        raise AITalkGenerationError("Таймаут: ответ не получен в течение 1 часа.")

    def structured_chat(self, messages: List[Message], response_format: str = "json") -> Dict[str, Any]:
        raise NotImplementedError("Structured chat is not supported in CUSTOM mode.")

    def _extract_answer(self, content: str) -> str:
        marker = "## Ответ"
        if marker not in content:
            return ""
        answer_part = content.split(marker, 1)[1].strip()
        answer_part = re.sub(r'<!--.*?-->', '', answer_part, flags=re.DOTALL).strip()
        return answer_part
