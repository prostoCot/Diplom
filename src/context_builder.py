"""
ContextBuilder — собирает словарь context для docxtpl.render().
Рисунки из отчёта исключены.
"""
import logging
import pandas as pd
from datetime import datetime

logger = logging.getLogger(__name__)


def _safe(df: pd.DataFrame, col: str, idx: int = 0, default: str = "—") -> str:
    try:
        val = df[col].iloc[idx]
        return str(val) if pd.notna(val) else default
    except Exception:
        return default


class ContextBuilder:
    def __init__(self, proc: dict, phrases: dict):
        self.proc    = proc
        self.phrases = phrases

    def build(self) -> dict:
        ctx = {}
        ctx.update(self.phrases)
        ctx.update(self._build_table1())
        ctx.update(self._build_table2())
        ctx.update(self._build_table3())
        ctx.update(self._build_table4())
        ctx.update(self._build_ch4_floor())
        ctx.update(self._build_ch4_mid())
        ctx.update(self._build_seismic())
        ctx.update(self._build_meta())
        logger.info("Контекст собран: %d ключей", len(ctx))
        return ctx

    # ── Таблица 1 ─────────────────────────────────────────────────────────────
    def _build_table1(self) -> dict:
        p   = self.proc.get("premise",           pd.DataFrame())
        geo = self.proc.get("geo_working",        pd.DataFrame())
        eq  = self.proc.get("equipment",          pd.DataFrame())
        cd  = self.proc.get("company",            pd.DataFrame())
        rd  = self.proc.get("regulatory",         pd.DataFrame())
        pvs = self.proc.get("premise_vent_shaft", pd.DataFrame())
        norm_val = _safe(rd, "normative_value") if not rd.empty else "0.5/4.0"
        return {
            "t1_layer_name":          _safe(geo, "layer_name"),
            "t1_length_m":            _safe(p,   "length_m"),
            "t1_pillar_length_m":     _safe(p,   "pillar_length_m"),
            "t1_daily_production":    _safe(p,   "daily_production"),
            "t1_coal_coef":           _safe(p,   "coal_production_coef"),
            "t1_plast_dev_type":      _safe(p,   "plast_development_type"),
            "t1_conveyor_ctrl":       _safe(p,   "conveyor_control_type"),
            "t1_rock_type":           _safe(geo, "rock_type"),
            "t1_vent_scheme":         _safe(p,   "ventilation_scheme"),
            "t1_complex_model":       _safe(eq,  "model"),
            "t1_cross_sec_vent":      _safe(pvs, "cross_section_m2"),
            "t1_cross_sec_lava":      _safe(p,   "cross_section_m2"),
            "t1_air_speed_norm":      norm_val,
            "t1_conveyor_speed_lava": _safe(p,   "conveyor_speed"),
            "t1_employees_count":     _safe(cd,  "employees_count"),
            "t1_thickness_m":         _safe(geo, "thickness_m"),
            "t1_rock_mass_density":   _safe(p,   "rock_mass_density"),
            "t1_coal_density":        _safe(p,   "coal_density"),
        }

    # ── Таблица 2 ─────────────────────────────────────────────────────────────
    def _build_table2(self) -> dict:
        geo = self.proc.get("geo_working",    pd.DataFrame())
        sr  = self.proc.get("sensor_ch4",     pd.DataFrame())
        sat = self.proc.get("geo_satellites", pd.DataFrame())

        def get_sensor(loc_substr: str) -> str:
            if sr.empty:
                return "—"
            mask = sr["location"].str.contains(loc_substr, case=False, na=False)
            s    = sr[mask]
            return str(round(s["value"].sum(), 2)) if not s.empty else "—"

        def get_sat(layer: str) -> str:
            if sat.empty:
                return "—"
            row = sat[sat["layer_name"] == layer]
            return str(round(float(row["gas_content_m3_per_ton"].iloc[0]), 2)) if not row.empty else "—"

        total = str(round(float(sr["value"].sum()), 2)) if not sr.empty else "—"

        rows = []
        rows.append({"name": "Газоносность, м³/т",
                     "value": _safe(geo, "gas_content_m3_per_ton")})
        rows.append({"name": "Метановыделение — разрабатываемый пласт (всего), м³/т",
                     "value": get_sensor("пласт")})
        rows.append({"name": "  в т.ч. в призабойное пространство, м³/т",
                     "value": get_sensor("призабойное")})
        rows.append({"name": "  в т.ч. в выработанное пространство, м³/т",
                     "value": get_sensor("выработанное")})
        for layer_name in ["К3/5", "К4", "К2"]:
            rows.append({"name": f"Из пластов {layer_name}, м³/т",
                         "value": get_sat(layer_name)})
        rows.append({"name": "Суммарное метановыделение на участке, м³/т",
                     "value": total})

        return {
            "t2_gas_content":   _safe(geo, "gas_content_m3_per_ton"),
            "t2_ch4_total":     total,
            "t2_gas_rows":      rows,
        }

    # ── Таблица 3 ─────────────────────────────────────────────────────────────
    def _build_table3(self) -> dict:
        vent = self.proc.get("ventilation", pd.DataFrame())

        def get_v(loc: str, col: str) -> str:
            if vent.empty:
                return "—"
            mask = vent["location"].str.contains(loc, case=False, na=False)
            row  = vent[mask]
            if row.empty:
                return "—"
            v = row[col].iloc[0]
            return str(round(float(v), 2)) if pd.notna(v) else "—"

        leak = distr = "—"
        if not vent.empty:
            leak  = str(vent["leakage_coefficient"].iloc[0])
            distr = str(vent["distribution_coefficient"].iloc[0])

        rows = []
        if not vent.empty:
            for _, row in vent.iterrows():
                rows.append({
                    "location": str(row.get("location", "—")),
                    "flow":     str(round(float(row["air_flow_m3_min"]), 1))
                                if pd.notna(row.get("air_flow_m3_min")) else "—",
                    "velocity": str(round(float(row["air_velocity_mps"]), 2))
                                if pd.notna(row.get("air_velocity_mps")) else "—",
                    "leakage":  str(row.get("leakage_coefficient",      "—")),
                    "distr":    str(row.get("distribution_coefficient",  "—")),
                })

        return {
            "t3_flow_uchastok":     get_v("участок", "air_flow_m3_min"),
            "t3_flow_lava":         get_v("очистн",  "air_flow_m3_min"),
            "t3_leakage_coef":      leak,
            "t3_distr_coef":        distr,
            "t3_velocity_uchastok": get_v("участок", "air_velocity_mps"),
            "t3_velocity_lava":     get_v("лава",    "air_velocity_mps"),
            "t3_vent_rows":         rows,
        }

    # ── Таблица 4 ─────────────────────────────────────────────────────────────
    def _build_table4(self) -> dict:
        pivot = self.proc.get("pressure_pivot", pd.DataFrame())
        d1    = self.proc.get("_date_prev1", "")
        d2    = self.proc.get("_date_prev2", "")
        try:
            d1_fmt = datetime.strptime(d1, "%Y-%m-%d").strftime("%d.%m.%Y")
            d2_fmt = datetime.strptime(d2, "%Y-%m-%d").strftime("%d.%m.%Y")
        except Exception:
            d1_fmt, d2_fmt = d1, d2

        rows = []
        if not pivot.empty:
            for hour in range(24):
                if hour in pivot.index:
                    row_data = pivot.loc[hour]
                    p1 = str(row_data.iloc[0]) if len(row_data) > 0 else "—"
                    p2 = str(row_data.iloc[1]) if len(row_data) > 1 else "—"
                else:
                    p1 = p2 = "—"
                rows.append({"time": f"{hour:02d}:00", "p1": p1, "p2": p2})

        return {
            "t4_date1":         d1_fmt,
            "t4_date2":         d2_fmt,
            "t4_pressure_rows": rows,
        }

    # ── CH4 на почве ──────────────────────────────────────────────────────────
    def _build_ch4_floor(self) -> dict:
        cols    = self.proc.get("ch4_floor_cols", [[], [], []])
        max_len = max((len(c) for c in cols), default=0)
        for col in cols:
            while len(col) < max_len:
                col.append({"section_no": "", "ch4_percent": ""})

        rows = []
        for i in range(max_len):
            row = {}
            for j, col in enumerate(cols, 1):
                row[f"sec{j}"]  = col[i]["section_no"]  if i < len(col) else ""
                row[f"ch4_{j}"] = col[i]["ch4_percent"] if i < len(col) else ""
            rows.append(row)

        return {
            "ch4_floor_rows": rows,
            "ch4_floor_col1": cols[0] if len(cols) > 0 else [],
            "ch4_floor_col2": cols[1] if len(cols) > 1 else [],
            "ch4_floor_col3": cols[2] if len(cols) > 2 else [],
        }

    # ── CH4 среднее сечение ───────────────────────────────────────────────────
    def _build_ch4_mid(self) -> dict:
        df   = self.proc.get("ch4_mid", pd.DataFrame())
        rows = []
        if not df.empty:
            for _, row in df.iterrows():
                rows.append({
                    "section_no":  str(row["section_no"]),
                    "ch4_percent": str(round(float(row["ch4_percent"]), 2)),
                })
        return {"ch4_mid_rows": rows}

    # ── Таблица 5 Сейсмика (без рисунка) ─────────────────────────────────────
    def _build_seismic(self) -> dict:
        df   = self.proc.get("seismic", pd.DataFrame())
        rows = []
        if not df.empty:
            for i, row in enumerate(df.itertuples(), 1):
                rows.append({
                    "num":      str(i),
                    "event_id": str(row.event_id),
                    "date":     str(row.event_date),
                    "time":     str(row.event_time),
                    "lat":      f"{float(row.latitude):.2f}",
                    "lon":      f"{float(row.longtitude):.2f}",
                    "depth":    str(row.depth_km),
                    "cls":      str(row.energy_class),
                    "mag":      str(row.magnitude),
                })
        return {"seismic_rows": rows}

    # ── Мета ──────────────────────────────────────────────────────────────────
    def _build_meta(self) -> dict:
        f = self.proc.get("flags", {})
        return {
            "ch4_max":     str(f.get("ch4_max",     "—")),
            "ch4_max_sec": str(f.get("ch4_max_sec", "—")),
            "p_trend":     str(f.get("p_trend",     "—")),
            "p_start":     str(f.get("p_start",     "—")),
            "p_end":       str(f.get("p_end",       "—")),
            "v_fact":      str(f.get("v_fact",      "—")),
        }
