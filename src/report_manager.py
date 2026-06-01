"""
ReportManager — фасад, координирует весь ETL-пайплайн.
Метод run(incident_id) реализует шаги 1–10 из раздела 2.3.2.
"""
import logging
import yaml
from pathlib import Path

from .database_connector import DatabaseConnector
from .query_executor     import QueryExecutor
from .data_processor     import DataProcessor
from .csv_exporter       import CSVExporter
from .phrase_builder     import PhraseBuilder
from .context_builder    import ContextBuilder
from .report_generator   import ReportGenerator

logger = logging.getLogger(__name__)


class ReportManager:
    """
    Центральный оркестратор модуля.
    Инициализируется один раз, метод run() вызывается для каждого инцидента.
    """

    def __init__(self, config: dict):
        self.config    = config
        self.connector = DatabaseConnector(config)
        self.exporter  = CSVExporter(config["paths"]["output_csv"])
        self.generator = ReportGenerator(
            template_path = config["paths"]["template"],
            output_dir    = config["paths"]["output_reports"],
        )

    # ── Шаг 2–3: Валидация ───────────────────────────────────────────────────
    def validate(self, incident_id: int) -> tuple:
        """
        Проверяет существование инцидента в БД.
        Возвращает (True, incident_row) или (False, error_message).
        """
        import pandas as pd
        try:
            conn = self.connector.connect()
            sql  = "SELECT * FROM incident_description WHERE incident_id = ?"
            df   = pd.read_sql_query(sql, conn, params=(incident_id,))
            self.connector.close()
            if df.empty:
                return False, f"Инцидент с ID={incident_id} не найден в базе данных."
            return True, df.iloc[0].to_dict()
        except Exception as e:
            self.connector.close()
            return False, f"Ошибка подключения к БД: {e}"

    # ── Основной пайплайн ─────────────────────────────────────────────────────
    def run(self, incident_id: int,
            progress_callback=None) -> Path:
        """
        Полный ETL-пайплайн генерации отчёта.
        progress_callback(step, total, message) — опциональный колбэк для UI.
        """
        def progress(step, msg):
            logger.info("[Шаг %d] %s", step, msg)
            if progress_callback:
                progress_callback(step, 10, msg)

        # ── Шаг 3: Подключение и валидация ───────────────────────────────────
        progress(3, "Подключение к БД и проверка инцидента...")
        ok, info = self.validate(incident_id)
        if not ok:
            raise ValueError(info)

        incident_date = info["incident_date"]
        mine_name     = info["mine_name"]
        logger.info("Инцидент найден: %s, шахта: %s", incident_date, mine_name)

        # ── Шаг 4: Извлечение данных (Extract) ───────────────────────────────
        progress(4, "Извлечение данных из БД (SQL-запросы)...")
        conn = self.connector.connect()
        mode = self.config["database"]["mode"]
        executor = QueryExecutor(conn, mode=mode)
        raw_data = executor.fetch_all(incident_id, incident_date, mine_name)
        self.connector.close()

        # ── Шаг 5: Сохранение CSV ─────────────────────────────────────────────
        progress(5, "Сохранение промежуточных данных в CSV...")
        self.exporter.export(raw_data, incident_id)

        # ── Шаг 6: Обработка данных (Transform) ──────────────────────────────
        progress(6, "Обработка данных (ETL: пивот, разбиение CH4, расчёт предикатов)...")
        processor  = DataProcessor(raw_data, self.config)
        processed  = processor.get_processed()

        # ── Шаг 7: Генерация шаблонных фраз ──────────────────────────────────
        progress(7, "Формирование шаблонных фраз...")
        builder  = PhraseBuilder(processed)
        phrases  = builder.build_all()

        # ── Шаг 8: Формирование контекста шаблона (Load prep) ────────────────
        progress(8, "Сборка контекста шаблона...")
        ctx_builder = ContextBuilder(processed, phrases)
        context     = ctx_builder.build()

        # ── Шаг 9: Рендеринг шаблона (Load) ──────────────────────────────────
        progress(9, "Рендеринг Word-шаблона (docxtpl)...")
        output_path = self.generator.render(context, incident_id)

        # ── Шаг 10: Завершение ────────────────────────────────────────────────
        progress(10, f"Отчёт готов: {output_path.name}")
        return output_path
