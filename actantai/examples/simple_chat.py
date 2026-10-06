"""
Простой пример использования ActantAI для общения с DeepSeek.
"""
import sys
import os

# Добавляем корень проекта в путь
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Импортируем ActantWeb
sys.path.insert(0, r"D:\repos\ActantWeb")
from actantweb import create_actant

from actantai.application.engine import ActantAIEngine
from actantai.infrastructure.actantweb_adapter import ActantWebAdapter
from actantai.infrastructure.providers.deepseek_provider import DeepSeekProvider


def main():
    print("🚀 Запуск ActantAI...")
    
    # Создаем экземпляр ActantWeb
    actant_web = create_actant()
    
    # Адаптируем его для ActantAI
    browser_adapter = ActantWebAdapter(actant_web)
    
    # Создаем движок ActantAI
    engine = ActantAIEngine()
    
    # Регистрируем провайдер DeepSeek
    deepseek = DeepSeekProvider(browser_adapter)
    engine.register_provider(deepseek)
    
    try:
        # Отправляем запрос
        print("\n📝 Отправка запроса в DeepSeek...")
        response = engine.ask("DeepSeek", "Привет! Как твои дела?")
        
        # Выводим ответ
        print("\n" + "=" * 60)
        print(f"🤖 Ответ от {response.provider_name}:")
        print("=" * 60)
        print(response.text)
        print("=" * 60)
        
        input("\nНажмите Enter для закрытия...")
        
    finally:
        # Закрываем браузер
        browser_adapter.stop()
        print("✅ Браузер закрыт")


if __name__ == "__main__":
    main()
