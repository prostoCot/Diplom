"""
PhraseBuilder — шаблонные фразы отчёта (Алгоритм 2, раздел 2.1.5).
Рисунки из отчёта исключены.
"""
import logging
import pandas as pd
from datetime import datetime

logger = logging.getLogger(__name__)


def _fmt_date(date_str: str) -> str:
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%d.%m.%Y")
    except Exception:
        return date_str


class PhraseBuilder:
    def __init__(self, data: dict):
        self.data  = data
        self.flags = data.get("flags", {})

    def phrase_t1_head(self) -> str:
        try:
            premise = self.data["premise"]
            geo     = self.data["geo_working"]
            name    = premise["premise_name"].iloc[0] if not premise.empty else "лава"
            layer   = geo["layer_name"].iloc[0]       if not geo.empty     else "пласт"
            return (f"Основные параметры лавы {name} (пласт {layer}) "
                    f"приведены в табл. 1.")
        except Exception as e:
            logger.warning("phrase_t1_head: %s", e)
            return "Основные параметры лавы приведены в табл. 1."

    def phrase_t2_head(self) -> str:
        try:
            prod = self.data["premise"]["daily_production"].iloc[0]
            return (f"Расчётный газовый баланс выемочного участка при плановой "
                    f"нагрузке {prod} т/сут приведён в табл. 2.")
        except Exception as e:
            logger.warning("phrase_t2_head: %s", e)
            return "Газовый баланс выемочного участка приведён в табл. 2."

    def phrase_t3_head(self) -> str:
        try:
            prod = self.data["premise"]["daily_production"].iloc[0]
            return (f"Параметры проветривания выемочного участка при плановой "
                    f"добыче {prod} т/сут приведены в табл. 3.")
        except Exception as e:
            logger.warning("phrase_t3_head: %s", e)
            return "Параметры проветривания приведены в табл. 3."

    def phrase_t3_vent(self) -> str:
        try:
            v_fact = self.flags.get("v_fact")
            flag_v = self.flags.get("flag_v")
            v_min, v_max = 0.5, 4.0
            reg = self.data.get("regulatory")
            if reg is not None and not reg.empty:
                parts = str(reg["normative_value"].iloc[0]).split("/")
                if len(parts) == 2:
                    v_min, v_max = float(parts[0]), float(parts[1])
            if v_fact is None:
                return "Данные о скорости воздуха в лаве отсутствуют."
            word = "соответствует" if flag_v == 1 else "НЕ соответствует"
            return (f"Фактическая скорость воздуха в нижней части лавы составила "
                    f"{v_fact} м/с, что {word} допустимому диапазону "
                    f"{v_min}–{v_max} м/с.")
        except Exception as e:
            logger.warning("phrase_t3_vent: %s", e)
            return "Параметры скорости воздуха уточняются."

    def phrase_t4_head(self) -> str:
        """Фраза перед Таблицей 4 (атмосферное давление)."""
        try:
            d1_fmt  = _fmt_date(self.data["_date_prev1"])
            d2_fmt  = _fmt_date(self.data["_date_prev2"])
            p_start = self.flags.get("p_start", "—")
            p_end   = self.flags.get("p_end",   "—")
            p_trend = self.flags.get("p_trend",  "изменялось")
            return (f"Атмосферное давление за {d1_fmt} и {d2_fmt} приведено "
                    f"в табл. 4. За рассматриваемый период давление "
                    f"{p_trend} с {p_start} до {p_end} мм рт. ст.")
        except Exception as e:
            logger.warning("phrase_t4_head: %s", e)
            return "Данные об атмосферном давлении приведены в табл. 4."

    def phrase_ch4_floor(self) -> str:
        try:
            ch4_max     = self.flags.get("ch4_max",     "—")
            section_max = self.flags.get("ch4_max_sec", "—")
            n           = len(self.data.get("ch4_floor", pd.DataFrame()))
            return (f"Результаты измерений концентрации метана на почве лавы "
                    f"приведены в табл. 1. Измерения проводились в {n} секциях. "
                    f"Максимальная концентрация {ch4_max}% зафиксирована "
                    f"в секции № {section_max}.")
        except Exception as e:
            logger.warning("phrase_ch4_floor: %s", e)
            return "Результаты измерений концентрации метана приведены в табл. 1."

    def phrase_ch4_mid(self) -> str:
        try:
            n = len(self.data.get("ch4_mid", pd.DataFrame()))
            return (f"Концентрация метана в среднем сечении лавы "
                    f"(высота отбора 10–150 см) приведена в табл. 2 "
                    f"для {n} контрольных точек.")
        except Exception as e:
            logger.warning("phrase_ch4_mid: %s", e)
            return "Концентрация метана в среднем сечении приведена в табл. 2."

    def phrase_seismic(self) -> str:
        """Фраза перед Таблицей 5 (сейсмические события)."""
        try:
            df    = self.data.get("seismic", pd.DataFrame())
            n     = len(df)
            d1_fmt = _fmt_date(self.data["_date_prev1"])
            d2_fmt = _fmt_date(self.data["_date_prev2"])
            m_max  = round(float(df["magnitude"].max()), 2) if not df.empty else "—"
            return (f"Землетрясения, произошедшие на территории Казахстана "
                    f"за период {d1_fmt}–{d2_fmt} по данным ТОО «СОМЭ», "
                    f"приведены в табл. 5. "
                    f"Зафиксировано {n} сейсмических событий, "
                    f"максимальная магнитуда — {m_max}.")
        except Exception as e:
            logger.warning("phrase_seismic: %s", e)
            return "Сейсмические события приведены в табл. 5."

    def build_all(self) -> dict:
        phrases = {
            "phrase_t1":        self.phrase_t1_head(),
            "phrase_t2":        self.phrase_t2_head(),
            "phrase_t3":        self.phrase_t3_head(),
            "phrase_t3_vent":   self.phrase_t3_vent(),
            "phrase_t4":        self.phrase_t4_head(),
            "phrase_ch4_floor": self.phrase_ch4_floor(),
            "phrase_ch4_mid":   self.phrase_ch4_mid(),
            "phrase_seismic":   self.phrase_seismic(),
        }
        logger.info("Сформировано %d шаблонных фраз", len(phrases))
        return phrases
