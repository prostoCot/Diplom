"""
init_db.py — создаёт SQLite БД и заполняет тестовыми данными.
4 инцидента на разных шахтах Казахстана (2022–2023).
Таблицы соответствуют ФМД и маппингу раздела 2.2 диплома.
Таблица graphic_reestr исключена.
"""
import sqlite3
import os

DB_PATH = "incident_db.sqlite"


def create_tables(conn):
    conn.executescript("""
    PRAGMA foreign_keys = ON;

    CREATE TABLE IF NOT EXISTS company_description (
        company_id      TEXT PRIMARY KEY,
        mine_name       TEXT NOT NULL,
        employees_count INTEGER,
        gas_category    TEXT,
        address         TEXT
    );

    CREATE TABLE IF NOT EXISTS premise (
        premise_id              INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id              TEXT REFERENCES company_description(company_id),
        premise_name            TEXT,
        premise_type            TEXT,
        length_m                REAL,
        pillar_length_m         REAL,
        daily_production        REAL,
        coal_production_coef    REAL,
        plast_development_type  TEXT,
        conveyor_control_type   TEXT,
        ventilation_scheme      TEXT,
        cross_section_m2        REAL,
        conveyor_speed          REAL,
        rock_mass_density       REAL,
        coal_density            REAL
    );

    CREATE TABLE IF NOT EXISTS regulatory_document (
        doc_id          INTEGER PRIMARY KEY AUTOINCREMENT,
        doc_name        TEXT NOT NULL,
        normative_value TEXT,
        unit            TEXT,
        description     TEXT
    );

    CREATE TABLE IF NOT EXISTS geological_structure (
        geo_id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        mine_name               TEXT,
        layer_name              TEXT,
        thickness_m             REAL,
        gas_content_m3_per_ton  REAL,
        rock_type               TEXT,
        depth_from_m            REAL,
        depth_to_m              REAL,
        is_working_layer        INTEGER DEFAULT 0,
        is_underworked          INTEGER DEFAULT 0,
        is_overworked           INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS equipment (
        equipment_id    INTEGER PRIMARY KEY AUTOINCREMENT,
        mine_name       TEXT,
        equipment_type  TEXT,
        model           TEXT,
        manufacturer    TEXT
    );

    CREATE TABLE IF NOT EXISTS seismic_event (
        event_id        INTEGER PRIMARY KEY AUTOINCREMENT,
        event_dttm      TEXT NOT NULL,
        latitude        REAL,
        longtitude      REAL,
        depth_km        REAL,
        energy_class    REAL,
        magnitude       REAL,
        source          TEXT
    );

    CREATE TABLE IF NOT EXISTS incident_description (
        incident_id          INTEGER PRIMARY KEY AUTOINCREMENT,
        incident_date        TEXT NOT NULL,
        incident_time        TEXT,
        mine_name            TEXT,
        location_description TEXT,
        incident_type        TEXT,
        brief_description    TEXT
    );

    CREATE TABLE IF NOT EXISTS ventilation_parameters (
        param_id                 INTEGER PRIMARY KEY AUTOINCREMENT,
        incident_id              INTEGER REFERENCES incident_description(incident_id),
        location                 TEXT,
        air_flow_m3_min          REAL,
        air_velocity_mps         REAL,
        leakage_coefficient      REAL,
        distribution_coefficient REAL
    );

    CREATE TABLE IF NOT EXISTS sensor_record (
        record_id    INTEGER PRIMARY KEY AUTOINCREMENT,
        incident_id  INTEGER REFERENCES incident_description(incident_id),
        sensor_type  TEXT,
        location     TEXT,
        premise_type TEXT,
        value        REAL,
        unit         TEXT,
        record_dttm  TEXT
    );

    CREATE TABLE IF NOT EXISTS chronology_incident (
        chrono_id     INTEGER PRIMARY KEY AUTOINCREMENT,
        incident_id   INTEGER REFERENCES incident_description(incident_id),
        event_dttm    TEXT NOT NULL,
        pressure_mmHg REAL,
        event_type    TEXT,
        description   TEXT
    );

    CREATE TABLE IF NOT EXISTS gas_analysis (
        analysis_id           INTEGER PRIMARY KEY AUTOINCREMENT,
        incident_id           INTEGER REFERENCES incident_description(incident_id),
        location              TEXT,
        ch4_percent           REAL,
        measurement_height_cm INTEGER,
        measurement_dttm      TEXT
    );
    """)
    print("✓ Таблицы созданы")


# ─────────────────────────────────────────────────────────────────────────────
# Вспомогательные функции вставки
# ─────────────────────────────────────────────────────────────────────────────

def insert_pressure(conn, incident_id, date_str, hour_pressures):
    """Вставляет почасовые данные давления для одной даты."""
    rows = [
        (incident_id, f"{date_str} {h:02d}:00:00", p, "pressure_measurement")
        for h, p in enumerate(hour_pressures)
    ]
    conn.executemany(
        "INSERT INTO chronology_incident (incident_id, event_dttm, pressure_mmHg, event_type) VALUES (?,?,?,?)",
        rows
    )


def insert_ch4_floor(conn, incident_id, sections, meas_date):
    """Вставляет замеры CH4 на почве (height=0)."""
    conn.executemany(
        "INSERT INTO gas_analysis (incident_id, location, ch4_percent, measurement_height_cm, measurement_dttm) VALUES (1,?,?,0,?)",
        [(str(sec), val, meas_date) for sec, val in sections]
    )
    # Правим incident_id
    conn.execute(
        "UPDATE gas_analysis SET incident_id=? WHERE incident_id=1 AND measurement_dttm=?",
        (incident_id, meas_date)
    )


def insert_ch4_mid(conn, incident_id, sections, meas_date):
    """Вставляет замеры CH4 в среднем сечении (height=80)."""
    conn.executemany(
        "INSERT INTO gas_analysis (incident_id, location, ch4_percent, measurement_height_cm, measurement_dttm) VALUES (?,?,?,80,?)",
        [(incident_id, str(sec), val, meas_date) for sec, val in sections]
    )


# ─────────────────────────────────────────────────────────────────────────────
# ИНЦИДЕНТ 1: Шахта 48к3-З — взрыв метана, 29.10.2023
# ─────────────────────────────────────────────────────────────────────────────

def incident_1(conn):
    conn.execute("INSERT OR REPLACE INTO company_description VALUES ('48k3z','Шахта 48к3-З',32,'III (сверхкатегорийная)','Карагандинская область')")

    conn.executemany("INSERT INTO premise (company_id,premise_name,premise_type,length_m,pillar_length_m,daily_production,coal_production_coef,plast_development_type,conveyor_control_type,ventilation_scheme,cross_section_m2,conveyor_speed,rock_mass_density,coal_density) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
        ('48k3z','Лава 48к3-З','лава',220,1200,2600,0.84,'Без разделения на слои','Полное обрушение','1К-Н-Н-вт',8.79,1.13,1.66,1.49),
        ('48k3z','Вентиляционный штрек 48к3-З','вентиляционный штрек',None,None,None,None,None,None,None,17.0,None,None,None),
        ('48k3z','Конвейерный штрек 48к3-З','Штрек',None,None,None,None,None,None,None,None,2.5,None,None),
    ])

    conn.executemany("INSERT INTO geological_structure (mine_name,layer_name,thickness_m,gas_content_m3_per_ton,rock_type,depth_from_m,depth_to_m,is_working_layer,is_underworked,is_overworked) VALUES (?,?,?,?,?,?,?,?,?,?)", [
        ('48k3z','К3/5 (рабочий)',2.1,15.99,'Песчанистые сланцы',500,502.1,1,0,0),
        ('48k3z','К3/5',1.3,3.11,'Аргиллит',510,511.3,0,1,0),
        ('48k3z','К4',0.9,2.53,'Алевролит',520,520.9,0,1,0),
        ('48k3z','К2',1.1,6.84,'Песчаник',490,491.1,0,0,1),
    ])

    conn.execute("INSERT INTO equipment (mine_name,equipment_type,model,manufacturer) VALUES ('48k3z','комплекс','Глиник 10/25-2','Glenik (Польша)')")

    conn.execute(
        "INSERT INTO incident_description (incident_id,incident_date,incident_time,mine_name,location_description,incident_type,brief_description) VALUES (?,?,?,?,?,?,?)",
        (1,'2023-10-29','02:15:00','48k3z','Лава 48к3-З, секция 66','Взрыв метановоздушной смеси',
         'Взрыв МВС в 02:15 на выемочном участке лавы 48к3-З при концентрации CH4 в секции 66 — 54.8%.')
    )

    conn.executemany("INSERT INTO ventilation_parameters (incident_id,location,air_flow_m3_min,air_velocity_mps,leakage_coefficient,distribution_coefficient) VALUES (?,?,?,?,?,?)", [
        (1,'участок',2705,3.03,1.3,1.0),
        (1,'очистная выработка',2080,3.94,1.3,1.0),
        (1,'лава нижняя часть',2080,3.94,1.3,1.0),
    ])

    conn.executemany("INSERT INTO sensor_record (incident_id,sensor_type,location,premise_type,value,unit) VALUES (?,?,?,?,?,?)", [
        (1,'CH4','разрабатываемый пласт (призабойное пространство)','Пласт',6.55,'m3/t'),
        (1,'CH4','разрабатываемый пласт (выработанное пространство)','Пласт',2.43,'m3/t'),
        (1,'CH4','выработанное пространство (суммарно)','Пласт',22.32,'m3/t'),
        (1,'CH4','подрабатываемые пласты К3/5','Пласт',3.11,'m3/t'),
        (1,'CH4','подрабатываемые пласты К4','Пласт',2.53,'m3/t'),
        (1,'CH4','надрабатываемые пласты К2','Пласт',6.84,'m3/t'),
        (1,'CH4','вмещающие породы','Пласт',3.45,'m3/t'),
        (1,'CH4','первичная посадка пород','Пласт',6.49,'m3/t'),
        (1,'CH4','участок (суммарно)','Участок',28.87,'m3/t'),
    ])

    # Давление 27.10.2023
    insert_pressure(conn, 1, '2023-10-27', [
        721,722,722,722,722,723,724,724,
        724,725,726,727,727,727,727,727,
        728,728,728,728.7,729.4,729.4,729.4,730.2
    ])
    # Давление 28.10.2023
    insert_pressure(conn, 1, '2023-10-28', [
        730.2,730.2,730.2,730.2,730.2,730.2,730.2,730.2,
        730.2,729.4,728.0,727.2,726.5,725.0,724.2,723.5,
        722.7,722.7,721.2
    ])

    # Сейсмика
    conn.executemany("INSERT INTO seismic_event (event_dttm,latitude,longtitude,depth_km,energy_class,magnitude,source) VALUES (?,?,?,?,?,?,?)", [
        ('2023-10-27 04:26:50',43.03,77.63,10,6.8,1.56,'ТОО СОМЭ'),
        ('2023-10-27 04:48:08',42.52,80.15,20,6.9,1.61,'ТОО СОМЭ'),
        ('2023-10-27 05:44:18',43.08,74.90, 0,5.8,1.00,'ТОО СОМЭ'),
        ('2023-10-27 06:58:22',46.03,74.03, 0,7.2,1.78,'ТОО СОМЭ'),
        ('2023-10-27 07:06:17',44.08,76.12,10,6.3,1.28,'ТОО СОМЭ'),
        ('2023-10-27 07:07:53',42.47,70.00,10,6.3,1.28,'ТОО СОМЭ'),
        ('2023-10-27 07:35:49',49.28,80.97, 5,7.6,2.00,'ТОО СОМЭ'),
        ('2023-10-27 19:07:25',45.88,80.30, 5,6.3,1.28,'ТОО СОМЭ'),
        ('2023-10-27 19:56:31',44.95,79.62,15,6.8,1.56,'ТОО СОМЭ'),
        ('2023-10-28 09:29:03',43.48,69.57, 0,7.0,1.67,'ТОО СОМЭ'),
        ('2023-10-28 12:25:45',43.27,78.60,10,6.2,1.23,'ТОО СОМЭ'),
        ('2023-10-28 22:22:33',43.18,78.35, 5,4.3,0.17,'ТОО СОМЭ'),
    ])

    # CH4 на почве (~72 секции)
    ch4_floor = [
        (2,7.09),(4,0.68),(6,2.0),(8,0.42),(10,0.91),(12,0.5),(14,0.39),
        (16,0.66),(18,0.45),(20,0.42),(22,0.45),(24,0.43),(26,3.43),(28,0.47),
        (30,0.36),(32,0.47),(34,0.43),(36,0.41),(38,0.32),(40,0.41),(42,0.34),
        (44,0.43),(46,0.46),(48,0.9),(50,5.73),(58,0.47),(60,0.4),(62,0.4),
        (64,0.97),(66,54.8),(68,0.44),(70,0.69),(72,0.44),(74,2.42),(76,0.65),
        (78,1.67),(80,0.49),(82,9.28),(84,1.2),(86,0.62),(88,0.97),(90,0.72),
        (92,5.6),(94,0.41),(96,0.35),(98,0.26),(100,0.36),(102,0.35),(104,0.42),
        (106,0.53),(108,0.6),(110,0.32),(112,0.56),(114,0.53),(116,0.42),
        (118,0.63),(120,0.66),(122,4.93),(124,9.18),(126,0.54),(128,3.98),
        (130,7.8),(132,1.2),(134,2.0),(136,1.95),(138,5.6),(139,2.9),
        (140,17.9),(141,5.6),(142,7.2),(143,0.25),(144,0.48),
    ]
    conn.executemany(
        "INSERT INTO gas_analysis (incident_id,location,ch4_percent,measurement_height_cm,measurement_dttm) VALUES (1,?,?,0,'2023-10-29 06:00:00')",
        [(str(s), v) for s, v in ch4_floor]
    )

    # CH4 в среднем сечении (9 точек)
    insert_ch4_mid(conn, 1, [
        (140,0.16),(135,0.20),(98,0.25),(84,0.26),
        (72,0.34),(60,0.36),(48,0.36),(36,0.37),(24,0.39),
    ], '2023-10-29 06:30:00')


# ─────────────────────────────────────────────────────────────────────────────
# ИНЦИДЕНТ 2: Шахта «Казахстанская» — вспышка метана, 14.03.2023
# ─────────────────────────────────────────────────────────────────────────────

def incident_2(conn):
    conn.execute("INSERT OR REPLACE INTO company_description VALUES ('kaz_mine','Шахта Казахстанская',28,'III (сверхкатегорийная)','Карагандинская область')")

    conn.executemany("INSERT INTO premise (company_id,premise_name,premise_type,length_m,pillar_length_m,daily_production,coal_production_coef,plast_development_type,conveyor_control_type,ventilation_scheme,cross_section_m2,conveyor_speed,rock_mass_density,coal_density) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
        ('kaz_mine','Лава 204к-Ю','лава',200,1050,2200,0.81,'Без разделения на слои','Полное обрушение','1К-Н-Н',8.40,1.10,1.64,1.47),
        ('kaz_mine','Вент. штрек 204к-Ю','вентиляционный штрек',None,None,None,None,None,None,None,15.5,None,None,None),
    ])

    conn.executemany("INSERT INTO geological_structure (mine_name,layer_name,thickness_m,gas_content_m3_per_ton,rock_type,depth_from_m,depth_to_m,is_working_layer,is_underworked,is_overworked) VALUES (?,?,?,?,?,?,?,?,?,?)", [
        ('kaz_mine','К5 (рабочий)',2.3,13.45,'Алевролит',480,482.3,1,0,0),
        ('kaz_mine','К6',1.1,2.80,'Аргиллит',492,493.1,0,1,0),
        ('kaz_mine','К4',0.8,2.10,'Песчаник',505,505.8,0,1,0),
        ('kaz_mine','К3',1.2,5.60,'Алевролит',470,471.2,0,0,1),
    ])

    conn.execute("INSERT INTO equipment (mine_name,equipment_type,model,manufacturer) VALUES ('kaz_mine','комплекс','DBT GmbH 2x200','DBT (Германия)')")

    conn.execute(
        "INSERT INTO incident_description (incident_id,incident_date,incident_time,mine_name,location_description,incident_type,brief_description) VALUES (?,?,?,?,?,?,?)",
        (2,'2023-03-14','18:42:00','kaz_mine','Лава 204к-Ю, секция 88, верхняя часть',
         'Вспышка метановоздушной смеси',
         'Вспышка МВС в верхней части лавы 204к-Ю. Предположительная причина — скопление CH4 у купола.')
    )

    conn.executemany("INSERT INTO ventilation_parameters (incident_id,location,air_flow_m3_min,air_velocity_mps,leakage_coefficient,distribution_coefficient) VALUES (?,?,?,?,?,?)", [
        (2,'участок',2450,2.85,1.25,1.0),
        (2,'очистная выработка',1950,3.68,1.25,1.0),
        (2,'лава нижняя часть',1950,3.68,1.25,1.0),
    ])

    conn.executemany("INSERT INTO sensor_record (incident_id,sensor_type,location,premise_type,value,unit) VALUES (?,?,?,?,?,?)", [
        (2,'CH4','разрабатываемый пласт (призабойное пространство)','Пласт',5.20,'m3/t'),
        (2,'CH4','разрабатываемый пласт (выработанное пространство)','Пласт',2.10,'m3/t'),
        (2,'CH4','выработанное пространство (суммарно)','Пласт',18.50,'m3/t'),
        (2,'CH4','подрабатываемые пласты К3/5','Пласт',2.80,'m3/t'),
        (2,'CH4','подрабатываемые пласты К4','Пласт',2.10,'m3/t'),
        (2,'CH4','надрабатываемые пласты К2','Пласт',5.60,'m3/t'),
        (2,'CH4','вмещающие породы','Пласт',2.90,'m3/t'),
        (2,'CH4','участок (суммарно)','Участок',24.40,'m3/t'),
    ])

    insert_pressure(conn, 2, '2023-03-12', [
        748,748.5,749,749,749.5,750,750,750.5,
        750.5,751,751,750.5,750,749.5,749,748.5,
        748,747.5,747,747,746.5,746,746,745.5
    ])
    insert_pressure(conn, 2, '2023-03-13', [
        745.5,745,744.5,744,744,743.5,743,742.5,
        742,742,741.5,741,740.5,740,740,739.5,
        739,739,738.5,738,737.5,737,737,736.5
    ])

    conn.executemany("INSERT INTO seismic_event (event_dttm,latitude,longtitude,depth_km,energy_class,magnitude,source) VALUES (?,?,?,?,?,?,?)", [
        ('2023-03-12 03:14:22',43.12,76.45, 8,6.5,1.40,'ТОО СОМЭ'),
        ('2023-03-12 11:32:07',42.88,77.20,15,7.1,1.72,'ТОО СОМЭ'),
        ('2023-03-12 16:55:41',44.30,75.88, 5,6.0,1.10,'ТОО СОМЭ'),
        ('2023-03-13 02:08:19',43.55,78.33,12,6.8,1.56,'ТОО СОМЭ'),
        ('2023-03-13 09:44:35',42.70,76.90, 0,5.5,0.90,'ТОО СОМЭ'),
        ('2023-03-13 14:21:58',45.10,79.15, 7,7.3,1.84,'ТОО СОМЭ'),
        ('2023-03-13 20:03:12',43.88,77.44,10,6.2,1.23,'ТОО СОМЭ'),
        ('2023-03-13 23:17:46',44.55,76.01, 3,5.9,1.05,'ТОО СОМЭ'),
        ('2023-03-14 07:30:00',43.20,77.80, 5,6.7,1.50,'ТОО СОМЭ'),
        ('2023-03-14 12:45:18',42.95,78.12,20,7.0,1.67,'ТОО СОМЭ'),
    ])

    ch4_floor_2 = [
        (2,0.35),(4,0.41),(6,0.38),(8,0.55),(10,0.72),(12,0.44),(14,0.39),
        (16,0.51),(18,0.68),(20,0.43),(22,0.37),(24,0.49),(26,1.82),(28,0.46),
        (30,0.40),(32,0.38),(34,0.44),(36,0.52),(38,0.35),(40,0.47),(42,0.39),
        (44,0.55),(46,0.61),(48,0.73),(50,2.18),(52,0.44),(54,0.38),(56,0.42),
        (58,0.50),(60,3.47),(62,0.45),(64,0.40),(66,0.53),(68,0.48),(70,0.36),
        (72,1.95),(74,0.44),(76,0.39),(78,0.57),(80,0.43),(82,4.31),(84,0.38),
        (86,0.51),(88,42.6),(90,0.47),(92,0.39),(94,0.55),(96,3.10),(98,0.42),
        (100,0.37),(102,0.48),(104,0.43),(106,0.55),(108,2.77),(110,0.40),
        (112,0.36),(114,0.52),(116,0.44),(118,0.38),(120,0.47),
    ]
    conn.executemany(
        "INSERT INTO gas_analysis (incident_id,location,ch4_percent,measurement_height_cm,measurement_dttm) VALUES (2,?,?,0,'2023-03-14 20:00:00')",
        [(str(s), v) for s, v in ch4_floor_2]
    )
    insert_ch4_mid(conn, 2, [
        (120,0.18),(110,0.22),(96,0.27),(82,0.31),
        (70,0.35),(60,0.38),(48,0.40),(36,0.41),(24,0.43),
    ], '2023-03-14 20:30:00')


# ─────────────────────────────────────────────────────────────────────────────
# ИНЦИДЕНТ 3: Шахта «Саранская» — горный удар, 07.06.2022
# ─────────────────────────────────────────────────────────────────────────────

def incident_3(conn):
    conn.execute("INSERT OR REPLACE INTO company_description VALUES ('sar_mine','Шахта Саранская',35,'II (газовая)','Карагандинская область')")

    conn.executemany("INSERT INTO premise (company_id,premise_name,premise_type,length_m,pillar_length_m,daily_production,coal_production_coef,plast_development_type,conveyor_control_type,ventilation_scheme,cross_section_m2,conveyor_speed,rock_mass_density,coal_density) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
        ('sar_mine','Лава 301с-В','лава',240,1400,3000,0.86,'Без разделения на слои','Полное обрушение','2К-Н-Н-вт',9.10,1.25,1.68,1.51),
        ('sar_mine','Вент. штрек 301с-В','вентиляционный штрек',None,None,None,None,None,None,None,18.2,None,None,None),
    ])

    conn.executemany("INSERT INTO geological_structure (mine_name,layer_name,thickness_m,gas_content_m3_per_ton,rock_type,depth_from_m,depth_to_m,is_working_layer,is_underworked,is_overworked) VALUES (?,?,?,?,?,?,?,?,?,?)", [
        ('sar_mine','Д6 (рабочий)',2.5,11.20,'Тонкозернистый песчаник',620,622.5,1,0,0),
        ('sar_mine','Д7',1.4,2.40,'Алевролит',635,636.4,0,1,0),
        ('sar_mine','Д5',1.0,3.80,'Аргиллит',608,609.0,0,0,1),
    ])

    conn.execute("INSERT INTO equipment (mine_name,equipment_type,model,manufacturer) VALUES ('sar_mine','комплекс','КМ-144','ЮРГТУ (Россия)')")

    conn.execute(
        "INSERT INTO incident_description (incident_id,incident_date,incident_time,mine_name,location_description,incident_type,brief_description) VALUES (?,?,?,?,?,?,?)",
        (3,'2022-06-07','10:30:00','sar_mine','Лава 301с-В, зона повышенного горного давления, секции 40-55',
         'Горный удар',
         'Горный удар на выемочном участке лавы 301с-В в зоне ПГД. Выброс угля ~8 т, повреждение крепи.')
    )

    conn.executemany("INSERT INTO ventilation_parameters (incident_id,location,air_flow_m3_min,air_velocity_mps,leakage_coefficient,distribution_coefficient) VALUES (?,?,?,?,?,?)", [
        (3,'участок',3100,3.35,1.35,1.0),
        (3,'очистная выработка',2400,4.15,1.35,1.0),
        (3,'лава нижняя часть',2400,4.15,1.35,1.0),
    ])

    conn.executemany("INSERT INTO sensor_record (incident_id,sensor_type,location,premise_type,value,unit) VALUES (?,?,?,?,?,?)", [
        (3,'CH4','разрабатываемый пласт (призабойное пространство)','Пласт',4.10,'m3/t'),
        (3,'CH4','разрабатываемый пласт (выработанное пространство)','Пласт',1.85,'m3/t'),
        (3,'CH4','выработанное пространство (суммарно)','Пласт',15.70,'m3/t'),
        (3,'CH4','подрабатываемые пласты К3/5','Пласт',2.40,'m3/t'),
        (3,'CH4','надрабатываемые пласты К2','Пласт',3.80,'m3/t'),
        (3,'CH4','вмещающие породы','Пласт',1.90,'m3/t'),
        (3,'CH4','участок (суммарно)','Участок',19.75,'m3/t'),
    ])

    insert_pressure(conn, 3, '2022-06-05', [
        753,753.5,754,754,754.5,755,755,755.5,
        755.5,756,756,755.5,755,754.5,754,753.5,
        753,752.5,752,752,751.5,751,751,750.5
    ])
    insert_pressure(conn, 3, '2022-06-06', [
        750.5,750,749.5,749,749,748.5,748,748,
        748,748.5,749,749,749.5,750,750,750.5,
        751,751,751.5,752,752,752.5,753,753
    ])

    conn.executemany("INSERT INTO seismic_event (event_dttm,latitude,longtitude,depth_km,energy_class,magnitude,source) VALUES (?,?,?,?,?,?,?)", [
        ('2022-06-05 01:22:10',49.80,72.85, 5,6.4,1.35,'КазНИИ'),
        ('2022-06-05 08:44:33',49.65,73.10,12,7.0,1.67,'КазНИИ'),
        ('2022-06-05 15:20:55',50.10,72.40, 3,5.8,1.02,'КазНИИ'),
        ('2022-06-06 04:11:28',49.90,73.55,10,6.9,1.61,'КазНИИ'),
        ('2022-06-06 10:35:47',49.75,72.20, 8,6.3,1.28,'КазНИИ'),
        ('2022-06-06 17:05:19',50.20,73.80, 0,7.5,1.95,'КазНИИ'),
        ('2022-06-06 22:48:02',49.55,72.95,15,6.1,1.18,'КазНИИ'),
        ('2022-06-07 03:30:41',49.88,73.22, 7,6.7,1.50,'КазНИИ'),
        ('2022-06-07 07:55:18',50.05,72.68, 4,7.2,1.78,'КазНИИ'),
        ('2022-06-07 09:10:05',49.72,73.40, 6,8.1,2.35,'КазНИИ'),
        ('2022-06-07 10:25:33',49.80,72.90, 2,9.0,2.80,'КазНИИ'),
    ])

    ch4_floor_3 = [
        (2,0.28),(4,0.33),(6,0.45),(8,0.38),(10,0.52),(12,0.41),(14,0.35),
        (16,0.48),(18,0.39),(20,0.44),(22,0.36),(24,0.51),(26,0.43),(28,0.37),
        (30,0.55),(32,0.41),(34,0.46),(36,0.39),(38,0.34),(40,1.85),(42,2.40),
        (44,3.15),(46,4.80),(48,6.20),(50,5.45),(52,3.10),(54,1.95),(56,0.88),
        (58,0.52),(60,0.44),(62,0.39),(64,0.48),(66,0.41),(68,0.36),(70,0.53),
        (72,0.45),(74,0.38),(76,0.43),(78,0.50),(80,0.37),(82,0.44),(84,0.39),
        (86,0.47),(88,0.41),(90,0.35),(92,0.52),(94,0.44),(96,0.38),(98,0.48),
        (100,0.42),(102,0.36),(104,0.45),(106,0.39),(108,0.53),(110,0.41),
    ]
    conn.executemany(
        "INSERT INTO gas_analysis (incident_id,location,ch4_percent,measurement_height_cm,measurement_dttm) VALUES (3,?,?,0,'2022-06-07 12:00:00')",
        [(str(s), v) for s, v in ch4_floor_3]
    )
    insert_ch4_mid(conn, 3, [
        (110,0.14),(100,0.18),(88,0.22),(76,0.27),
        (64,0.31),(52,0.35),(40,0.38),(28,0.40),(16,0.42),
    ], '2022-06-07 12:30:00')


# ─────────────────────────────────────────────────────────────────────────────
# ИНЦИДЕНТ 4: Шахта «Абайская» — внезапный выброс угля и газа, 19.11.2022
# ─────────────────────────────────────────────────────────────────────────────

def incident_4(conn):
    conn.execute("INSERT OR REPLACE INTO company_description VALUES ('abay_mine','Шахта Абайская',30,'III (сверхкатегорийная)','Карагандинская область')")

    conn.executemany("INSERT INTO premise (company_id,premise_name,premise_type,length_m,pillar_length_m,daily_production,coal_production_coef,plast_development_type,conveyor_control_type,ventilation_scheme,cross_section_m2,conveyor_speed,rock_mass_density,coal_density) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
        ('abay_mine','Лава 510а-З','лава',210,1100,2400,0.83,'Без разделения на слои','Полное обрушение','1К-Н-Н',8.65,1.18,1.65,1.48),
        ('abay_mine','Вент. штрек 510а-З','вентиляционный штрек',None,None,None,None,None,None,None,16.0,None,None,None),
    ])

    conn.executemany("INSERT INTO geological_structure (mine_name,layer_name,thickness_m,gas_content_m3_per_ton,rock_type,depth_from_m,depth_to_m,is_working_layer,is_underworked,is_overworked) VALUES (?,?,?,?,?,?,?,?,?,?)", [
        ('abay_mine','К10 (рабочий)',2.0,17.30,'Углистый аргиллит',545,547.0,1,0,0),
        ('abay_mine','К11',1.2,4.20,'Алевролит',558,559.2,0,1,0),
        ('abay_mine','К9',0.9,3.50,'Песчаник',535,535.9,0,0,1),
    ])

    conn.execute("INSERT INTO equipment (mine_name,equipment_type,model,manufacturer) VALUES ('abay_mine','комплекс','Fazos-17/37-Oz','Famur (Польша)')")

    conn.execute(
        "INSERT INTO incident_description (incident_id,incident_date,incident_time,mine_name,location_description,incident_type,brief_description) VALUES (?,?,?,?,?,?,?)",
        (4,'2022-11-19','22:05:00','abay_mine','Лава 510а-З, секции 70-85, угольный пласт К10',
         'Внезапный выброс угля и газа',
         'Внезапный выброс угля (~15 т) и газа в лаве 510а-З. Концентрация CH4 в секции 78 составила 61.3%.')
    )

    conn.executemany("INSERT INTO ventilation_parameters (incident_id,location,air_flow_m3_min,air_velocity_mps,leakage_coefficient,distribution_coefficient) VALUES (?,?,?,?,?,?)", [
        (4,'участок',2600,2.95,1.28,1.0),
        (4,'очистная выработка',2000,3.80,1.28,1.0),
        (4,'лава нижняя часть',2000,3.80,1.28,1.0),
    ])

    conn.executemany("INSERT INTO sensor_record (incident_id,sensor_type,location,premise_type,value,unit) VALUES (?,?,?,?,?,?)", [
        (4,'CH4','разрабатываемый пласт (призабойное пространство)','Пласт',7.80,'m3/t'),
        (4,'CH4','разрабатываемый пласт (выработанное пространство)','Пласт',3.20,'m3/t'),
        (4,'CH4','выработанное пространство (суммарно)','Пласт',25.60,'m3/t'),
        (4,'CH4','подрабатываемые пласты К3/5','Пласт',4.20,'m3/t'),
        (4,'CH4','надрабатываемые пласты К2','Пласт',3.50,'m3/t'),
        (4,'CH4','вмещающие породы','Пласт',4.10,'m3/t'),
        (4,'CH4','первичная посадка пород','Пласт',5.80,'m3/t'),
        (4,'CH4','участок (суммарно)','Участок',32.10,'m3/t'),
    ])

    insert_pressure(conn, 4, '2022-11-17', [
        735,735.5,736,736,736.5,737,737,737.5,
        738,738,738.5,738,737.5,737,736.5,736,
        735.5,735,734.5,734,734,733.5,733,732.5
    ])
    insert_pressure(conn, 4, '2022-11-18', [
        732.5,732,731.5,731,730.5,730,730,729.5,
        729,728.5,728,727.5,727,726.5,726,725.5,
        725,724.5,724,724,723.5,723,722.5,722
    ])

    conn.executemany("INSERT INTO seismic_event (event_dttm,latitude,longtitude,depth_km,energy_class,magnitude,source) VALUES (?,?,?,?,?,?,?)", [
        ('2022-11-17 05:18:44',49.45,72.10, 6,6.6,1.45,'КазНИИ'),
        ('2022-11-17 12:30:22',49.60,72.55,10,7.1,1.72,'КазНИИ'),
        ('2022-11-17 19:44:11',49.30,71.90, 3,6.0,1.10,'КазНИИ'),
        ('2022-11-18 03:22:38',49.75,72.80,15,6.8,1.56,'КазНИИ'),
        ('2022-11-18 08:55:17',49.50,73.10, 8,5.9,1.05,'КазНИИ'),
        ('2022-11-18 14:10:05',49.20,71.75, 0,7.4,1.89,'КазНИИ'),
        ('2022-11-18 20:33:49',49.65,72.40,12,6.5,1.40,'КазНИИ'),
        ('2022-11-19 01:48:27',49.40,72.95, 5,7.0,1.67,'КазНИИ'),
        ('2022-11-19 07:05:14',49.55,71.85, 7,6.3,1.28,'КазНИИ'),
        ('2022-11-19 13:22:58',49.70,73.20, 4,6.9,1.61,'КазНИИ'),
        ('2022-11-19 18:40:33',49.35,72.15, 9,7.6,2.05,'КазНИИ'),
        ('2022-11-19 21:55:10',49.80,72.70, 2,8.3,2.48,'КазНИИ'),
    ])

    ch4_floor_4 = [
        (2,0.32),(4,0.45),(6,0.38),(8,0.51),(10,0.44),(12,0.39),(14,0.47),
        (16,0.55),(18,0.42),(20,0.37),(22,0.49),(24,0.43),(26,0.58),(28,0.41),
        (30,0.36),(32,0.52),(34,0.44),(36,0.39),(38,0.47),(40,0.53),(42,0.40),
        (44,0.46),(46,0.38),(48,0.55),(50,0.43),(52,0.48),(54,0.35),(56,0.51),
        (58,0.44),(60,0.39),(62,1.85),(64,3.42),(66,5.17),(68,8.90),(70,12.4),
        (72,18.7),(74,25.3),(76,38.6),(78,61.3),(80,42.1),(82,19.8),(84,8.75),
        (86,3.20),(88,1.45),(90,0.62),(92,0.48),(94,0.41),(96,0.37),(98,0.44),
        (100,0.39),(102,0.52),(104,0.43),(106,0.38),(108,0.47),(110,0.41),
        (112,0.36),(114,0.48),(116,0.42),(118,0.37),(120,0.51),(122,0.44),
    ]
    conn.executemany(
        "INSERT INTO gas_analysis (incident_id,location,ch4_percent,measurement_height_cm,measurement_dttm) VALUES (4,?,?,0,'2022-11-19 23:30:00')",
        [(str(s), v) for s, v in ch4_floor_4]
    )
    insert_ch4_mid(conn, 4, [
        (122,0.17),(110,0.21),(96,0.26),(84,0.30),
        (72,0.34),(60,0.37),(48,0.39),(36,0.41),(24,0.43),
    ], '2022-11-19 23:45:00')


# ─────────────────────────────────────────────────────────────────────────────

def insert_regulatory(conn):
    conn.execute("""
        INSERT OR IGNORE INTO regulatory_document
        (doc_name, normative_value, unit, description)
        VALUES (
            'Правила безопасности: скорость воздуха в лаве',
            '0.5/4.0', 'м/с',
            'ПБ §158: допустимая скорость воздуха в очистных выработках'
        )
    """)


def main():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Старая БД удалена: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    try:
        create_tables(conn)
        insert_regulatory(conn)
        incident_1(conn)
        print("  ✓ Инцидент 1: Шахта 48к3-З — взрыв МВС (29.10.2023)")
        incident_2(conn)
        print("  ✓ Инцидент 2: Шахта Казахстанская — вспышка МВС (14.03.2023)")
        incident_3(conn)
        print("  ✓ Инцидент 3: Шахта Саранская — горный удар (07.06.2022)")
        incident_4(conn)
        print("  ✓ Инцидент 4: Шахта Абайская — выброс угля и газа (19.11.2022)")
        conn.commit()

        # Итоговая проверка
        for iid in [1, 2, 3, 4]:
            n_ch4   = conn.execute("SELECT COUNT(*) FROM gas_analysis WHERE incident_id=? AND measurement_height_cm=0", (iid,)).fetchone()[0]
            n_press = conn.execute("SELECT COUNT(*) FROM chronology_incident WHERE incident_id=?", (iid,)).fetchone()[0]
            print(f"    ID={iid}: CH4_почва={n_ch4} сек., давление={n_press} ч.")

        n_seis = conn.execute("SELECT COUNT(*) FROM seismic_event").fetchone()[0]
        print(f"\n✓ Сейсмика (все инциденты): {n_seis} событий")
        print(f"✓ БД готова: {DB_PATH}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
