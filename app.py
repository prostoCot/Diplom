"""
app.py — точка входа Streamlit (StreamlitUI).
Полноценный интерфейс модуля подготовки отчётной документации.
"""
import sys
import logging
import yaml
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

import streamlit as st


def setup_logging(config: dict) -> None:
    log_path = ROOT / config["paths"]["logs"]
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=getattr(logging, config["logging"]["level"], logging.INFO),
        format=config["logging"]["format"],
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(),
        ],
        force=True,
    )


@st.cache_resource
def load_config():
    with open(ROOT / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


@st.cache_resource
def get_manager(config_key):
    config = load_config()
    from src.report_manager import ReportManager
    return ReportManager(config)


def get_all_incidents(config):
    """Возвращает список всех инцидентов из БД для таблицы выбора."""
    import sqlite3
    import pandas as pd
    try:
        db = ROOT / config["database"]["sqlite_path"]
        conn = sqlite3.connect(str(db))
        df = pd.read_sql_query(
            "SELECT incident_id, incident_date, mine_name, incident_type "
            "FROM incident_description ORDER BY incident_id",
            conn
        )
        conn.close()
        return df
    except Exception:
        return None


def main():
    st.set_page_config(
        page_title="Модуль подготовки отчётной документации",
        page_icon="📋",
        layout="wide",
    )

    config = load_config()
    setup_logging(config)

    # ── Шапка ────────────────────────────────────────────────────────────────
    st.markdown("""
        <h2 style='text-align:center; color:#1F4E79; margin-bottom:0'>
            Модуль подготовки отчётной документации
        </h2>
        <p style='text-align:center; color:#555; margin-top:4px; font-size:15px'>
            Система расследования аварий и инцидентов на производственных объектах
        </p>
        <hr style='border:1px solid #D0E4F7; margin-top:8px'>
    """, unsafe_allow_html=True)

    # ── Две колонки: левая — список инцидентов, правая — форма ───────────────
    col_left, col_right = st.columns([1.4, 1], gap="large")

    with col_left:
        st.markdown("#### Зарегистрированные инциденты")
        incidents_df = get_all_incidents(config)
        if incidents_df is not None and not incidents_df.empty:
            # Переименовываем колонки для отображения
            display_df = incidents_df.rename(columns={
                "incident_id":   "ID",
                "incident_date": "Дата",
                "mine_name":     "Объект",
                "incident_type": "Тип инцидента",
            })
            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("База данных не инициализирована. Выполните: `python init_db.py`")

    with col_right:
        st.markdown("#### Формирование отчёта")

        with st.container(border=True):
            incident_id = st.number_input(
                "Идентификатор инцидента (ID)",
                min_value=1,
                max_value=999999,
                value=1,
                step=1,
                help="Введите ID из таблицы инцидентов слева",
            )

            generate_btn = st.button(
                "Сформировать отчёт",
                type="primary",
                use_container_width=True,
            )

        # ── Генерация ─────────────────────────────────────────────────────
        if generate_btn:
            manager = get_manager("singleton")

            # Валидация
            with st.spinner("Проверка данных..."):
                ok, info = manager.validate(int(incident_id))

            if not ok:
                st.error(f"❌ {info}")
                return

            # Краткая карточка инцидента
            with st.container(border=True):
                st.markdown("**Инцидент найден**")
                st.write(f"📅 **Дата:** {info.get('incident_date', '—')}")
                st.write(f"🏭 **Объект:** {info.get('mine_name', '—')}")
                st.write(f"⚠️ **Тип:** {info.get('incident_type', '—')}")

            # Прогресс
            st.markdown("**Выполнение:**")
            progress_bar = st.progress(0)
            status_text  = st.empty()
            steps_log    = []

            def progress_callback(step, total, message):
                progress_bar.progress(int(step / total * 100))
                status_text.text(message)
                steps_log.append(f"[{step}/{total}] {message}")

            try:
                output_path = manager.run(
                    incident_id=int(incident_id),
                    progress_callback=progress_callback,
                )

                progress_bar.progress(100)
                status_text.empty()
                st.success("Отчёт сформирован успешно.")

                # Кнопка скачивания
                with open(output_path, "rb") as f:
                    docx_bytes = f.read()

                st.download_button(
                    label=f"⬇️  Скачать {output_path.name}",
                    data=docx_bytes,
                    file_name=output_path.name,
                    mime="application/vnd.openxmlformats-officedocument"
                         ".wordprocessingml.document",
                    type="primary",
                    use_container_width=True,
                )

                # Детали выполнения
                with st.expander("Подробный лог выполнения"):
                    for line in steps_log:
                        st.text(line)

            except FileNotFoundError as e:
                progress_bar.empty()
                st.error(f"Шаблон отчёта не найден: {e}")
                st.code("Запустите: python create_template.py")

            except ValueError as e:
                progress_bar.empty()
                st.error(f"Ошибка данных: {e}")

            except Exception as e:
                progress_bar.empty()
                st.error(f"Ошибка при формировании отчёта: {e}")
                with st.expander("Подробности"):
                    import traceback
                    st.code(traceback.format_exc())

    # ── Нижняя полоса ────────────────────────────────────────────────────────
    st.markdown("""
        <hr style='border:1px solid #E0E0E0; margin-top:30px'>
        <p style='text-align:center; color:#999; font-size:12px'>
            Система расследования аварий и инцидентов &nbsp;|&nbsp;
            Модуль подготовки отчётной документации
        </p>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
