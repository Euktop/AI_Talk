from dataclasses import dataclass

@dataclass(frozen=True)
class DeepSeekSelectors:
    """Стабильные XPath-селекторы для DeepSeek, адаптированные под ActantWebAdapter (XPath 1.0)."""
    url: str = "https://chat.deepseek.com/"
    
    # --- 1. Ввод и отправка сообщений ---
    input_field: str = "//textarea[contains(@placeholder, 'Message DeepSeek') or contains(@placeholder, 'Отправьте сообщение') or @name='search']"
    send_button: str = "//div[@role='button' and not(contains(@class, 'ds-button--disabled')) and (contains(@class, 'ds-button--primary') or contains(@class, 'ds-button--iconLabelPrimary'))]"
    stop_button: str = "//div[@role='button' and .//svg[contains(@d, 'M5.5498 9.75V5')]]"
    upload_button: str = "//div[@role='button' and .//svg[contains(@viewBox, '0 0 16 16') and not(contains(@d, 'M5.5498'))]]"
    file_input: str = "//input[@type='file']"
    
    # --- 2. Переключатели режимов и моделей ---
    deep_think_toggle: str = "//div[@role='button' and contains(translate(., 'DEEPTHINK', 'deepthink'), 'deepthink')]"
    search_toggle: str = "//div[@role='button' and contains(translate(., 'SEARCH', 'search'), 'search')]"
    model_radio_group: str = "//div[@role='radiogroup']"
    model_instant: str = "//div[@role='radio' and (@data-model-type='default' or contains(., 'Instant'))]"
    model_expert: str = "//div[@role='radio' and (@data-model-type='expert' or contains(., 'Expert'))]"
    model_vision: str = "//div[@role='radio' and (@data-model-type='vision' or contains(., 'Vision'))]"
    
    # --- 3. Боковая панель и история ---
    new_chat_button: str = "//div[@role='button' and contains(., 'New chat') or contains(., 'Новый чат')]"
    sidebar_toggle: str = "//div[@role='button' and .//svg[contains(@d, 'M3')]]"
    history_container: str = "//nav[contains(@class, 'sidebar') or contains(@aria-label, 'History')]"
    history_item: str = "//nav//a[contains(@href, '/chat/')]"
    
    # --- 4. Действия с сообщениями ---
    copy_code_button: str = "//div[contains(@class, 'ds-code-block')]//button[@aria-label='Copy code' or @title='Copy']"
    copy_message_button: str = "(//div[contains(@class, 'ds-message')]//div[@role='button' and .//svg[contains(@d, 'M12.8531')]])[last()]"
    regenerate_button: str = "(//div[contains(@class, 'ds-message')]//div[@role='button' and .//svg[contains(@d, 'M8')]])[last()]"
    edit_prompt_button: str = "(//div[contains(@class, 'ds-message')]//div[@role='button' and .//svg[contains(@d, 'M11')]])[last()]"
    
    # --- 5. Управление загруженными файлами ---
    uploaded_file_container: str = "//div[contains(@class, 'file') and contains(@class, 'container')]"
    uploaded_file_item: str = "//div[contains(@class, 'file') and contains(@class, 'item')]"
    uploaded_file_name: str = "//div[contains(@class, 'file')]//span[contains(@class, 'name')]"
    uploaded_file_size: str = "//div[contains(@class, 'file')]//span[contains(@class, 'size')]"
    uploaded_file_remove_button: str = "//div[contains(@class, 'file')]//button[@aria-label='Remove' or @title='Remove']"
    
    # --- 6. Пагинация длинных сообщений ---
    pagination_container: str = "//div[contains(@class, 'pagination')]"
    pagination_prev: str = "(//div[contains(@class, 'pagination')]//div[@role='button'])[1]"
    pagination_indicator: str = "//div[contains(@class, 'pagination')]//div[contains(@class, 'indicator')]"
    pagination_next: str = "(//div[contains(@class, 'pagination')]//div[@role='button'])[last()]"
    
    # --- 7. Индикаторы (обязательны для логики ожидания в DeepSeekProvider) ---
    response_container: str = "(//div[contains(@class, 'ds-message')])[last()]"
    loading_indicator: str = "//div[contains(@class, 'ds-loading') or contains(@class, 'typing')]"