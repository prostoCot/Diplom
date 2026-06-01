"""
QueryExecutor — параметризованные SQL-запросы → pandas DataFrame.
"""
import logging
import pandas as pd

logger = logging.getLogger(__name__)

SQL_MAP = {
    "incident": """
        SELECT incident_id, incident_date, incident_time, mine_name,
               location_description, incident_type, brief_description
        FROM incident_description
        WHERE incident_id = :incident_id
    """,
    "premise": """
        SELECT premise_id, premise_name, premise_type, length_m,
               pillar_length_m, daily_production, coal_production_coef,
               plast_development_type, conveyor_control_type,
               ventilation_scheme, cross_section_m2, conveyor_speed,
               rock_mass_density, coal_density, company_id
        FROM premise
        WHERE premise_type = 'лава' AND company_id = :mine_name
    """,
    "company": """
        SELECT company_id, mine_name, employees_count, gas_category
        FROM company_description
        WHERE mine_name = :mine_name
    """,
    "geo_working": """
        SELECT layer_name, thickness_m, gas_content_m3_per_ton,
               rock_type, depth_from_m, depth_to_m, is_working_layer
        FROM geological_structure
        WHERE mine_name = :mine_name AND is_working_layer = 1
    """,
    "geo_satellites": """
        SELECT layer_name, gas_content_m3_per_ton,
               depth_from_m, is_underworked, is_overworked
        FROM geological_structure
        WHERE mine_name = :mine_name
          AND layer_name IN ('К3/5', 'К4', 'К2')
        ORDER BY depth_from_m DESC
    """,
    "equipment": """
        SELECT equipment_id, equipment_type, model, manufacturer
        FROM equipment
        WHERE equipment_type = 'комплекс' AND mine_name = :mine_name
        LIMIT 1
    """,
    "regulatory": """
        SELECT doc_name, normative_value, unit
        FROM regulatory_document
        WHERE doc_name LIKE '%скорость воздуха в лаве%'
        LIMIT 1
    """,
    "ventilation": """
        SELECT location, air_flow_m3_min, air_velocity_mps,
               leakage_coefficient, distribution_coefficient
        FROM ventilation_parameters
        WHERE incident_id = :incident_id
        ORDER BY location
    """,
    "sensor_ch4": """
        SELECT location, sensor_type, value, unit, premise_type
        FROM sensor_record
        WHERE incident_id = :incident_id
          AND sensor_type = 'CH4' AND unit = 'm3/t'
        ORDER BY location
    """,
    "pressure": """
        SELECT strftime('%Y-%m-%d', event_dttm) AS day,
               CAST(strftime('%H', event_dttm) AS INTEGER) AS hour,
               pressure_mmHg, event_dttm
        FROM chronology_incident
        WHERE incident_id = :incident_id
          AND pressure_mmHg IS NOT NULL
          AND date(event_dttm) IN (:date_prev1, :date_prev2)
        ORDER BY event_dttm
    """,
    "ch4_floor": """
        SELECT location AS section_no, ch4_percent, measurement_height_cm
        FROM gas_analysis
        WHERE incident_id = :incident_id
          AND measurement_height_cm = 0
        ORDER BY CAST(location AS INTEGER)
    """,
    "ch4_mid": """
        SELECT location AS section_no, ch4_percent, measurement_height_cm
        FROM gas_analysis
        WHERE incident_id = :incident_id
          AND measurement_height_cm BETWEEN 10 AND 150
        ORDER BY CAST(location AS INTEGER) DESC
    """,
    "seismic": """
        SELECT event_id, event_dttm, latitude, longtitude,
               depth_km, energy_class, magnitude, source
        FROM seismic_event
        WHERE date(event_dttm) IN (:date_prev1, :date_prev2)
        ORDER BY event_dttm
    """,
    "premise_vent_shaft": """
        SELECT cross_section_m2, premise_name
        FROM premise
        WHERE premise_type = 'вентиляционный штрек'
          AND company_id = :mine_name
        LIMIT 1
    """,
}


class QueryExecutor:
    def __init__(self, conn, mode: str = "sqlite"):
        self.conn    = conn
        self.mode    = mode
        self.sql_map = SQL_MAP

    def fetch(self, key: str, params: dict) -> pd.DataFrame:
        sql = self.sql_map.get(key)
        if sql is None:
            raise KeyError(f"Запрос '{key}' не найден в SQL_MAP")
        try:
            if self.mode == "sqlite":
                df = pd.read_sql_query(sql, self.conn, params=params)
            else:
                cursor = self.conn.cursor()
                sql_t, values = self._adapt_for_trino(sql, params)
                cursor.execute(sql_t, values)
                rows = cursor.fetchall()
                cols = [d[0] for d in cursor.description]
                df = pd.DataFrame(rows, columns=cols)
            logger.info("Запрос [%s]: %d строк", key, len(df))
            return df
        except Exception as e:
            logger.error("Ошибка запроса [%s]: %s", key, e)
            raise

    def _adapt_for_trino(self, sql: str, params: dict):
        import re
        keys = re.findall(r':(\w+)', sql)
        sql_out = re.sub(r':\w+', '?', sql)
        return sql_out, [params[k] for k in keys]

    def fetch_all(self, incident_id: int, incident_date: str,
                  mine_name: str) -> dict:
        from datetime import datetime, timedelta
        inc_dt     = datetime.strptime(incident_date, "%Y-%m-%d")
        date_prev1 = (inc_dt - timedelta(days=2)).strftime("%Y-%m-%d")
        date_prev2 = (inc_dt - timedelta(days=1)).strftime("%Y-%m-%d")

        p_inc   = {"incident_id": incident_id}
        p_mine  = {"mine_name": mine_name}
        p_press = {"incident_id": incident_id,
                   "date_prev1": date_prev1, "date_prev2": date_prev2}
        p_seis  = {"date_prev1": date_prev1, "date_prev2": date_prev2}

        result = {}
        for key, params in [
            ("premise",            p_mine),
            ("company",            p_mine),
            ("geo_working",        p_mine),
            ("geo_satellites",     p_mine),
            ("equipment",          p_mine),
            ("regulatory",         {}),
            ("ventilation",        p_inc),
            ("sensor_ch4",         p_inc),
            ("pressure",           p_press),
            ("ch4_floor",          p_inc),
            ("ch4_mid",            p_inc),
            ("seismic",            p_seis),
            ("premise_vent_shaft", p_mine),
        ]:
            result[key] = self.fetch(key, params)

        result["_date_prev1"] = date_prev1
        result["_date_prev2"] = date_prev2
        return result
