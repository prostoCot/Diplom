"""
DataProcessor — применяет математические модели из раздела 2.1.3 диплома:
  (2.1) Расчёт скорости воздуха
  (2.2) Предикат соответствия нормативу
  (2.3) Суммарное метановыделение
  (2.4–2.5) Динамика давления
  (2.6) Пивот-таблица давления
  (2.7) Разбиение таблицы CH4 на колонки
"""
import math
import logging
from datetime import datetime
import pandas as pd

logger = logging.getLogger(__name__)


class DataProcessor:
    """Принимает сырые DataFrames, возвращает обработанные."""

    def __init__(self, raw: dict, config: dict):
        self.raw = raw
        self.config = config
        self.v_min = config["report"]["air_speed_min"]   # 0.5 м/с
        self.v_max = config["report"]["air_speed_max"]   # 4.0 м/с
        self.ch4_n_cols = config["report"]["ch4_columns"]  # 3

    # ─── Публичный метод ─────────────────────────────────────────────────────
    def get_processed(self) -> dict:
        """Возвращает словарь обработанных данных."""
        proc = {}
        proc["premise"]        = self._process_premise()
        proc["company"]        = self.raw["company"].copy()
        proc["geo_working"]    = self.raw["geo_working"].copy()
        proc["geo_satellites"] = self.raw["geo_satellites"].copy()
        proc["equipment"]      = self.raw["equipment"].copy()
        proc["regulatory"]     = self.raw["regulatory"].copy()
        proc["ventilation"]    = self._process_ventilation()
        proc["sensor_ch4"]     = self._process_gas_balance()
        proc["pressure_pivot"] = self._pivot_pressure()
        proc["pressure_raw"]   = self.raw["pressure"].copy()
        proc["ch4_floor_cols"] = self._split_ch4(self.raw["ch4_floor"])
        proc["ch4_floor"]      = self.raw["ch4_floor"].copy()
        proc["ch4_mid"]        = self.raw["ch4_mid"].copy()
        proc["seismic"]        = self._process_seismic()

        proc["premise_vent_shaft"] = self.raw["premise_vent_shaft"].copy()
        proc["flags"]          = self.calc_flags()
        proc["_date_prev1"]    = self.raw["_date_prev1"]
        proc["_date_prev2"]    = self.raw["_date_prev2"]
        return proc

    # ─── Обработка параметров лавы ───────────────────────────────────────────
    def _process_premise(self) -> pd.DataFrame:
        df = self.raw["premise"].copy()
        return df

    # ─── Обработка вентиляции: формула (2.1) ────────────────────────────────
    def _process_ventilation(self) -> pd.DataFrame:
        """
        Если air_velocity_mps отсутствует — вычисляем по формуле (2.1):
        v = Q / (S × 60), где Q — air_flow_m3_min, S — cross_section_m2 лавы.
        """
        df = self.raw["ventilation"].copy()
        premise = self.raw["premise"]

        # Сечение очистной выработки (лавы)
        s_lava = (
            premise["cross_section_m2"].iloc[0]
            if not premise.empty else 8.79
        )

        def calc_velocity(row):
            if pd.notna(row.get("air_velocity_mps")) and row["air_velocity_mps"] > 0:
                return round(float(row["air_velocity_mps"]), 2)
            if pd.notna(row.get("air_flow_m3_min")) and float(row["air_flow_m3_min"]) > 0:
                # Формула (2.1): v = Q / (S × 60)
                return round(float(row["air_flow_m3_min"]) / (float(s_lava) * 60), 2)
            return None

        df["air_velocity_calc"] = df.apply(calc_velocity, axis=1)
        logger.info("Вентиляция обработана: %d записей", len(df))
        return df

    # ─── Газовый баланс: формула (2.3) ──────────────────────────────────────
    def _process_gas_balance(self) -> pd.DataFrame:
        """
        Агрегируем показания датчиков CH4 по локации.
        Суммарное метановыделение Q_ch4 = сумма по всем источникам.
        """
        df = self.raw["sensor_ch4"].copy()
        if df.empty:
            return df

        # Округляем значения
        df["value"] = df["value"].apply(lambda x: round(float(x), 2) if pd.notna(x) else x)
        return df

    # ─── Пивот давления: формула (2.6) ──────────────────────────────────────
    def _pivot_pressure(self) -> pd.DataFrame:
        """
        Преобразует df_pressure в сводную таблицу: индекс = час (0-23),
        столбцы = даты (date_prev1, date_prev2).
        """
        df = self.raw["pressure"].copy()
        if df.empty:
            logger.warning("Нет данных об атмосферном давлении")
            return pd.DataFrame()

        d1 = self.raw["_date_prev1"]
        d2 = self.raw["_date_prev2"]

        try:
            pivot = df.pivot_table(
                index="hour",
                columns="day",
                values="pressure_mmHg",
                aggfunc="first"
            )
            # Гарантируем наличие обоих столбцов
            for d in [d1, d2]:
                if d not in pivot.columns:
                    pivot[d] = None
            pivot = pivot[[d1, d2]]
            pivot = pivot.reindex(range(24))
            # Форматируем: None → "—"
            for col in pivot.columns:
                pivot[col] = pivot[col].apply(
                    lambda x: str(round(float(x), 1)) if pd.notna(x) else "—"
                )
            logger.info("Пивот давления построен: %d часов", len(pivot))
            return pivot
        except Exception as e:
            logger.error("Ошибка построения пивот-таблицы давления: %s", e)
            return pd.DataFrame()

    # ─── Разбиение CH4: формула (2.7) ───────────────────────────────────────
    def _split_ch4(self, df: pd.DataFrame) -> list:
        """
        Разбивает DataFrame CH4 на self.ch4_n_cols групп.
        Возвращает список списков словарей.
        N_col = ceil(len(df) / n_cols)
        """
        if df.empty:
            return [[] for _ in range(self.ch4_n_cols)]

        n = len(df)
        n_col = math.ceil(n / self.ch4_n_cols)

        cols = []
        for i in range(self.ch4_n_cols):
            chunk = df.iloc[i * n_col:(i + 1) * n_col]
            cols.append([
                {"section_no": str(row["section_no"]),
                 "ch4_percent": str(round(float(row["ch4_percent"]), 2))}
                for _, row in chunk.iterrows()
            ])
        logger.info("CH4 разбит на %d колонки по %d строк", self.ch4_n_cols, n_col)
        return cols

    # ─── Обработка сейсмики ──────────────────────────────────────────────────
    def _process_seismic(self) -> pd.DataFrame:
        df = self.raw["seismic"].copy()
        if df.empty:
            return df
        df["event_date"] = pd.to_datetime(df["event_dttm"]).dt.strftime("%d.%m.%Y")
        df["event_time"] = pd.to_datetime(df["event_dttm"]).dt.strftime("%H:%M:%S")
        return df

    # ─── Расчёт предикатов (2.2, 2.4–2.5) ───────────────────────────────────
    def calc_flags(self) -> dict:
        """
        Возвращает словарь вычисленных предикатов и производных показателей.
        """
        flags = {}

        # (2.2) Соответствие скорости воздуха нормативу
        vent = self.raw["ventilation"]
        try:
            lava_row = vent[vent["location"].str.contains("лава", case=False, na=False)]
            if not lava_row.empty:
                v_fact = float(lava_row.iloc[0].get("air_velocity_mps") or 0)
                flags["v_fact"] = round(v_fact, 2)
                flags["flag_v"] = 1 if self.v_min <= v_fact <= self.v_max else 0
            else:
                flags["v_fact"] = None
                flags["flag_v"] = None
        except Exception:
            flags["v_fact"] = None
            flags["flag_v"] = None

        # (2.4–2.5) Динамика атмосферного давления
        pressure = self.raw["pressure"]
        try:
            if not pressure.empty:
                p_start = float(pressure.iloc[0]["pressure_mmHg"])
                p_end   = float(pressure.iloc[-1]["pressure_mmHg"])
                dp      = p_end - p_start
                flags["p_start"] = round(p_start, 1)
                flags["p_end"]   = round(p_end, 1)
                flags["dp"]      = round(dp, 1)
                # (2.5)
                if dp > 1:
                    flags["p_trend"]      = "возросло"
                    flags["p_trend_adj"]  = "рост"
                elif dp < -1:
                    flags["p_trend"]      = "снизилось"
                    flags["p_trend_adj"]  = "падение"
                else:
                    flags["p_trend"]      = "оставалось стабильным"
                    flags["p_trend_adj"]  = "стабильное"
            else:
                flags.update({"p_start": None, "p_end": None, "dp": None,
                               "p_trend": "неизвестно", "p_trend_adj": "неизвестно"})
        except Exception as e:
            logger.warning("Ошибка расчёта динамики давления: %s", e)

        # (2.3) Максимальное значение CH4 на почве
        ch4_floor = self.raw["ch4_floor"]
        try:
            if not ch4_floor.empty:
                idx_max = ch4_floor["ch4_percent"].idxmax()
                flags["ch4_max"]     = round(float(ch4_floor.loc[idx_max, "ch4_percent"]), 2)
                flags["ch4_max_sec"] = str(ch4_floor.loc[idx_max, "section_no"])
            else:
                flags["ch4_max"] = None
                flags["ch4_max_sec"] = "—"
        except Exception:
            flags["ch4_max"] = None
            flags["ch4_max_sec"] = "—"

        return flags
