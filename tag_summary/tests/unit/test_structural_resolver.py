"""Юнит-тесты для StructuralTagResolver."""

from __future__ import annotations

from tag_summary.domain.services.structural_tag_resolver import StructuralTagResolver


class TestStructuralTagResolver:
    def setup_method(self) -> None:
        self.r = StructuralTagResolver()

    def _values(self, rel_path: str) -> set[str]:
        return {t.value for t in self.r.resolve(rel_path)}

    def test_project_folder(self) -> None:
        assert self._values("20 Проекты/AI_Talk.md") == {"project"}

    def test_panel_folder(self) -> None:
        assert self._values("10 Панель управления/🏠 Моя жизнь.md") == {"moc"}

    def test_reports_folder(self) -> None:
        assert self._values("10 Панель управления/Отчёты/Отчёт.md") == {"system", "analysis"}

    def test_daily_folder(self) -> None:
        assert self._values("30 Зоны ответственности/Дневник/05.07.2026.md") == {"daily"}

    def test_prompts_folder(self) -> None:
        assert self._values("40 Ресурсы/Промпты/My Prompt.md") == {"resource", "ai"}

    def test_resources_root(self) -> None:
        assert self._values("40 Ресурсы/registry.md") == {"resource"}

    def test_archive(self) -> None:
        assert self._values("50 Архив/Что-то.md") == {"archive"}

    def test_special_case_root_rules(self) -> None:
        assert self._values("00_RULES.md") == {"system", "rules"}

    def test_special_case_ai_context(self) -> None:
        assert self._values("AI_CONTEXT.md") == {"system", "ai"}

    def test_unknown_path_returns_empty(self) -> None:
        assert self._values("Random/file.md") == set()
