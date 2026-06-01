"""
DatabaseConnector — инкапсулирует параметры подключения к БД.
Поддерживает SQLite (эмуляция) и Trino (боевой режим).
"""
import sqlite3
import logging
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class DatabaseConnector:
    """
    Устанавливает соединение с БД.
    Режим определяется параметром config.database.mode:
      'sqlite' — локальная эмуляция через SQLite
      'trino'  — подключение к Trino через trino-python-client
    """

    def __init__(self, config: dict):
        self.config = config
        self.mode = config["database"]["mode"]
        self._conn = None

    def connect(self):
        """Открывает соединение и возвращает объект connection."""
        if self.mode == "sqlite":
            return self._connect_sqlite()
        elif self.mode == "trino":
            return self._connect_trino()
        else:
            raise ValueError(f"Неизвестный режим БД: {self.mode}")

    def _connect_sqlite(self):
        db_path = self.config["database"]["sqlite_path"]
        logger.info("Подключение к SQLite: %s", db_path)
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            # Включаем поддержку внешних ключей
            conn.execute("PRAGMA foreign_keys = ON")
            self._conn = conn
            logger.info("SQLite: соединение установлено")
            return conn
        except sqlite3.Error as e:
            logger.error("Ошибка подключения к SQLite: %s", e)
            raise

    def _connect_trino(self):
        """
        Подключение к Trino.
        Требует установленного пакета trino и заполненного .env (DB_PASSWORD).
        """
        try:
            import trino  # noqa: F401
            from trino.dbapi import connect as trino_connect
            from trino.auth import BasicAuthentication

            cfg = self.config["database"]["trino"]
            password = os.getenv("DB_PASSWORD", "")
            auth = BasicAuthentication(cfg["user"], password) if password else None

            conn = trino_connect(
                host=cfg["host"],
                port=cfg["port"],
                user=cfg["user"],
                catalog=cfg["catalog"],
                schema=cfg["schema"],
                auth=auth,
                http_scheme="https" if password else "http",
            )
            self._conn = conn
            logger.info("Trino: соединение установлено (%s:%s)", cfg["host"], cfg["port"])
            return conn
        except ImportError:
            raise RuntimeError(
                "Пакет 'trino' не установлен. Установите: pip install trino"
            )
        except Exception as e:
            logger.error("Ошибка подключения к Trino: %s", e)
            raise

    def close(self):
        """Закрывает соединение."""
        if self._conn:
            try:
                self._conn.close()
                logger.info("Соединение с БД закрыто")
            except Exception as e:
                logger.warning("Ошибка при закрытии соединения: %s", e)
            finally:
                self._conn = None
