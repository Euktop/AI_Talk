import os
import time
from typing import Any
from actantai.domain.ports import ILLMProvider, IBrowserEngine, Prompt, AIResponse
from actantai.domain.exceptions import ProviderNotAvailableError, ResponseTimeoutError, SelectorNotFoundError
from actantai.infrastructure.manifests.deepseek_manifest import DeepSeekSelectors


class DeepSeekProvider(ILLMProvider):
    """Провайдер для работы с DeepSeek через браузер с поддержкой расширенных функций."""
    
    def __init__(self, browser: IBrowserEngine):
        self._browser = browser
        self._selectors = DeepSeekSelectors()
        self._is_initialized = False
    
    def get_name(self) -> str:
        return "DeepSeek"
    
    def is_available(self) -> bool:
        return self._browser is not None
    
    def _initialize(self) -> None:
        if not self._is_initialized:
            self._browser.go_to(self._selectors.url)
            self._browser.wait(self._selectors.input_field, timeout=15)
            self._is_initialized = True
    
    def send_prompt(self, prompt: Prompt) -> AIResponse:
        try:
            self._initialize()

            # 1. Включаем DeepThink (надежный JS-подход, устойчивый к перекрытиям)
            if prompt.enable_deep_think:
                try:
                    result = self._browser.js("""
                    const buttons = document.querySelectorAll('div[role="button"]');
                    for (let btn of buttons) {
                        const text = btn.textContent.toLowerCase();
                        if (text.includes('deepthink') || text.includes('глубокое')) {
                            if (btn.getAttribute('aria-pressed') !== 'true') {
                                btn.click();
                                return 'activated';
                            }
                            return 'already_active';
                        }
                    }
                    return 'not_found';
                    """)
                    if result == 'activated':
                        print("  ✅ DeepThink активирован.")
                    elif result == 'already_active':
                        pass # Нормальное состояние
                    else:
                        print("  ⚠️ Кнопка DeepThink не найдена.")
                except Exception as e:
                    print(f"  ⚠️ Ошибка при активации DeepThink: {e}")

            # 2. Включаем Search (аналогично)
            if prompt.enable_search:
                try:
                    result = self._browser.js("""
                    const buttons = document.querySelectorAll('div[role="button"]');
                    for (let btn of buttons) {
                        const text = btn.textContent.toLowerCase();
                        if (text.includes('search') || text.includes('поиск')) {
                            if (btn.getAttribute('aria-pressed') !== 'true') {
                                btn.click();
                                return 'activated';
                            }
                            return 'already_active';
                        }
                    }
                    return 'not_found';
                    """)
                except Exception as e:
                    print(f"  ⚠️ Ошибка при активации Search: {e}")

            # 3. Загрузка файла (если указана)
            if prompt.file_path and os.path.exists(prompt.file_path):
                try:
                    self._browser.upload_file(self._selectors.file_input, os.path.abspath(prompt.file_path))
                except Exception as e:
                    raise SelectorNotFoundError(f"Не удалось загрузить файл {prompt.file_path}: {e}")

            # 4. ОЧИСТКА ПОЛЯ ВВОДА (КРИТИЧНО для многоходовочек!)
            safe_input_xpath = self._selectors.input_field.replace("'", "\\'")
            self._browser.js(f"""
            const el = document.evaluate('{safe_input_xpath}', document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
            if (el) {{
                el.value = '';
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
            }}
            """)
            time.sleep(0.3) # Даем React осознать очистку

            # 5. Ввод нового текста
            self._browser.type(self._selectors.input_field, prompt.text)
            time.sleep(0.5) # Даем React осознать ввод
            
            # 6. Отправка
            try:
                self._browser.click(self._selectors.send_button)
            except Exception:
                # Fallback: эмуляция Enter через JS
                self._browser.js(f"""
                const el = document.evaluate('{safe_input_xpath}', document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                if (el) {{
                    el.focus();
                    el.dispatchEvent(new KeyboardEvent('keydown', {{key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true}}));
                    el.dispatchEvent(new KeyboardEvent('keypress', {{key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true}}));
                }}
                """)

            # ==========================================
            # 7. УМНОЕ ОЖИДАНИЕ СТРИМИНГА (Алгоритм стабилизации)
            # ==========================================
            timeout = 120
            start_time = time.time()
            response_sel = self._selectors.response_container

            # Фаза 1: Ждем появления первого значимого куска текста
            while time.time() - start_time < timeout:
                try:
                    text = self._browser.read(response_sel)
                    if text and len(text.strip()) > 10:
                        break
                except Exception:
                    pass
                time.sleep(0.5)
            else:
                raise ResponseTimeoutError("Таймаут: ответ не начал поступать.")

            # Фаза 2: Мониторинг стабильности длины текста
            last_length = 0
            stable_checks = 0
            required_stable_checks = 3

            while time.time() - start_time < timeout:
                try:
                    current_text = self._browser.read(response_sel)
                    current_length = len(current_text)

                    if current_length > last_length:
                        last_length = current_length
                        stable_checks = 0
                    else:
                        stable_checks += 1

                    if stable_checks >= required_stable_checks:
                        break

                    time.sleep(0.8)
                except Exception:
                    time.sleep(0.5)
            else:
                raise ResponseTimeoutError("Превышен лимит ожидания генерации!")

            time.sleep(0.5) # Финальная отрисовка

            # 8. Чтение финального ответа
            response_text = self._browser.read(response_sel)
            
            return AIResponse(
                text=response_text,
                provider_name=self.get_name(),
                tokens_used=0
            )
        except Exception as e:
            raise ResponseTimeoutError(f"Не удалось получить ответ от DeepSeek: {e}")
