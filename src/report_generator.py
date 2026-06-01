"""
ReportGenerator — загружает шаблон Word, рендерит через docxtpl, сохраняет DOCX.
"""
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class ReportGenerator:
    def __init__(self, template_path: str, output_dir: str):
        self.template_path = Path(template_path)
        self.output_dir    = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def render(self, context: dict, incident_id: int) -> Path:
        """
        Рендерит шаблон с контекстом и сохраняет DOCX.
        Возвращает путь к готовому файлу.
        """
        if not self.template_path.exists():
            raise FileNotFoundError(
                f"Шаблон не найден: {self.template_path}"
            )

        timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_name = f"report_{incident_id}_{timestamp}.docx"
        output_path = self.output_dir / output_name

        try:
            from docxtpl import DocxTemplate
            tpl = DocxTemplate(str(self.template_path))
            tpl.render(context)
            tpl.save(str(output_path))
            logger.info("Отчёт сохранён: %s", output_path)
            return output_path
        except Exception as e:
            logger.error("Ошибка рендеринга шаблона: %s", e)
            raise
