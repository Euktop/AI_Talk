import asyncio
from typing import Any
from actantai.domain.ports import IBrowserEngine
from actantai.domain.exceptions import SelectorNotFoundError

class ActantWebAdapter(IBrowserEngine):
    """Адаптер для интеграции с асинхронной библиотекой ActantWeb из синхронного ActantAI."""
    
    def __init__(self, actant_engine: Any):
        self._engine = actant_engine

    def _run_async(self, coro):
        """Безопасный мост для вызова async методов ActantWeb из синхронного кода."""
        try:
            # Проверяем, есть ли уже запущенный цикл событий в текущем потоке
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # Мы внутри async-контекста (Jupyter, FastAPI).
            # Запускаем в отдельном потоке с новым event loop, чтобы избежать deadlock.
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        else:
            # Мы в синхронном контексте, безопасно используем asyncio.run
            return asyncio.run(coro)

    def go_to(self, url: str) -> None:
        self._run_async(self._engine.go_to(url))

    def click(self, selector: str) -> None:
        try:
            self._run_async(self._engine.click("xpath", selector))
        except Exception as e:
            raise SelectorNotFoundError(f"Не удалось кликнуть по {selector}: {e}")

    def type(self, selector: str, text: str) -> None:
        try:
            self._run_async(self._engine.type("xpath", selector, text))
        except Exception as e:
            raise SelectorNotFoundError(f"Не удалось ввести текст в {selector}: {e}")

    def read(self, selector: str) -> str:
        try:
            return self._run_async(self._engine.read("xpath", selector))
        except Exception as e:
            raise SelectorNotFoundError(f"Не удалось прочитать {selector}: {e}")

    def wait(self, selector: str, timeout: int = 30) -> None:
        try:
            self._run_async(self._engine.wait("xpath", selector, timeout))
        except Exception as e:
            raise SelectorNotFoundError(f"Не удалось дождаться {selector}: {e}")

    def stop(self) -> None:
        self._run_async(self._engine.stop())

    def js(self, script: str) -> Any:
        try:
            return self._run_async(self._engine.js(script))
        except Exception as e:
            raise SelectorNotFoundError(f"Ошибка выполнения JS: {e}")

    def upload_file(self, selector: str, file_path: str) -> None:
        """Надежная загрузка файла через нативный send_keys Selenium."""
        try:
            # Делаем элемент видимым для Selenium, если он скрыт
            js_make_visible = f"""
            const el = document.evaluate('{selector}', document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
            if (el) {{ el.style.display = 'block'; el.style.visibility = 'visible'; }}
            """
            self._run_async(self._engine.js(js_make_visible))
            # Используем новый нативный метод upload_file из ActantWeb
            self._run_async(self._engine.upload_file("xpath", selector, file_path))
        except Exception as e:
            raise SelectorNotFoundError(f"Не удалось загрузить файл {file_path}: {e}")
