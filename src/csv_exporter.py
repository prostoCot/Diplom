"""CSVExporter — сохраняет каждый DataFrame в отдельный CSV."""
import logging
from pathlib import Path
import pandas as pd

logger = logging.getLogger(__name__)


class CSVExporter:
    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export(self, data: dict, incident_id: int) -> None:
        """Сохраняет все DataFrames из словаря data в CSV."""
        skip_keys = {"_date_prev1", "_date_prev2", "flags",
                     "ch4_floor_cols", "pressure_pivot"}
        for key, val in data.items():
            if key in skip_keys:
                continue
            if isinstance(val, pd.DataFrame):
                self.export_one(val, f"{incident_id}_{key}")

    def export_one(self, df: pd.DataFrame, name: str) -> Path:
        """Сохраняет один DataFrame. Возвращает путь к файлу."""
        path = self.output_dir / f"{name}.csv"
        try:
            df.to_csv(path, index=False, encoding="utf-8-sig")
            logger.info("CSV сохранён: %s (%d строк)", path.name, len(df))
            return path
        except Exception as e:
            logger.error("Ошибка сохранения CSV [%s]: %s", name, e)
            raise
