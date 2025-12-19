import json
import logging
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
import psycopg2.extras

from hospital_controller.internal.domain.config import RegulatorRepo as ConfigRegulatorRepo


class HospitalRepo:
    """PostgreSQL репозиторий больницы.

    Про JSON/JSONB:
    - Если колонки объявлены как JSON/JSONB, psycopg2 может вернуть Python-объекты (dict/list),
      если зарегистрировать адаптеры JSON.
    - Ниже мы используем register_default_json/jsonb и RealDictCursor,
      поэтому fetch* возвращает dict, а JSONB поля уже распарсены.
    - Если в вашей БД JSON хранится как TEXT/VARCHAR, тогда придётся делать json.loads вручную.
    """

    def __init__(self, config: ConfigRegulatorRepo):
        self.config = config
        self.connection = None
        self.cursor = None
        self.connect()

        if getattr(config, "InitSchema", True):
            self.init_schema()

    def connect(self):
        self.connection = psycopg2.connect(
            host=self.config.Host,
            port=self.config.Port,
            database=self.config.Name,
            user=self.config.User,
            password=self.config.Password,
        )
        psycopg2.extras.register_default_json(self.connection)
        psycopg2.extras.register_default_jsonb(self.connection)

        self.cursor = self.connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        self.connection.autocommit = True

    def close_connection(self):
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()

    def execute_and_fetch(self, sql: str, params: Optional[tuple] = None) -> Tuple[List[Dict[str, Any]], bool]:
        try:
            self.cursor.execute(sql, params)
            result = self.cursor.fetchall()
            return list(result), True
        except Exception as e:
            logging.error(f"DB execute_and_fetch error: {e}")
            return [], False

    def execute_and_fetch_one(self, sql: str, params: Optional[tuple] = None) -> Tuple[Optional[Dict[str, Any]], bool]:
        try:
            self.cursor.execute(sql, params)
            result = self.cursor.fetchone()
            return (dict(result) if result else None), True
        except Exception as e:
            logging.error(f"DB execute_and_fetch_one error: {e}")
            return None, False

    def execute(self, sql: str, params: Optional[tuple] = None) -> bool:
        try:
            self.cursor.execute(sql, params)
            return True
        except Exception as e:
            logging.error(f"DB execute error: {e}")
            return False

    # --- Schema ---
    def init_schema(self) -> bool:
        """Создаёт таблицы, если их нет."""
        sql = '''
        CREATE TABLE IF NOT EXISTS public."INSTITUTION" (
            id SERIAL PRIMARY KEY,
            did TEXT UNIQUE NOT NULL,
            verkey TEXT NOT NULL,
            alias TEXT,
            is_public BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS public."REGULATOR_PERMISSIONS" (
            id SERIAL PRIMARY KEY,
            vc_type TEXT NOT NULL,
            cred_ex_id TEXT UNIQUE,
            credential_id TEXT,
            raw_record JSONB,
            issued_at TIMESTAMPTZ DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS public."MEDICAL_DOCUMENTS" (
            doc_id UUID PRIMARY KEY,
            doc_type TEXT NOT NULL,
            payload JSONB NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS public."DOCUMENT_LEDGER_META" (
            id SERIAL PRIMARY KEY,
            doc_id UUID REFERENCES public."MEDICAL_DOCUMENTS"(doc_id) ON DELETE CASCADE,
            vc_type TEXT NOT NULL,
            schema_id TEXT,
            cred_def_id TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        '''
        return self.execute(sql)

    # --- Institution DID ---
    def upsert_institution_did(self, did: str, verkey: str, alias: str, is_public: bool = False) -> bool:
        sql = '''
        INSERT INTO public."INSTITUTION" (did, verkey, alias, is_public)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (did) DO UPDATE
        SET verkey=EXCLUDED.verkey, alias=EXCLUDED.alias, is_public=EXCLUDED.is_public;
        '''
        return self.execute(sql, (did, verkey, alias, is_public))

    def set_institution_public(self, did: str) -> bool:
        sql = 'UPDATE public."INSTITUTION" SET is_public=TRUE WHERE did=%s'
        return self.execute(sql, (did,))

    def get_institution(self) -> Tuple[Optional[Dict[str, Any]], bool]:
        sql = 'SELECT * FROM public."INSTITUTION" ORDER BY created_at DESC LIMIT 1'
        return self.execute_and_fetch_one(sql)

    # --- Permissions ---
    def save_permission_vc(self, vc_type: str, cred_ex_id: str, raw_record: dict, credential_id: Optional[str] = None) -> bool:
        sql = '''
        INSERT INTO public."REGULATOR_PERMISSIONS" (vc_type, cred_ex_id, credential_id, raw_record)
        VALUES (%s, %s, %s, %s::jsonb)
        ON CONFLICT (cred_ex_id) DO UPDATE
        SET vc_type=EXCLUDED.vc_type,
            credential_id=EXCLUDED.credential_id,
            raw_record=EXCLUDED.raw_record;
        '''
        return self.execute(sql, (vc_type, cred_ex_id, credential_id, json.dumps(raw_record)))

    def has_permission(self, vc_type: str) -> Tuple[bool, bool]:
        sql = 'SELECT 1 AS ok FROM public."REGULATOR_PERMISSIONS" WHERE vc_type=%s LIMIT 1'
        row, ok = self.execute_and_fetch_one(sql, (vc_type,))
        return (row is not None), ok

    def list_permissions(self) -> Tuple[List[Dict[str, Any]], bool]:
        sql = 'SELECT vc_type, issued_at, cred_ex_id FROM public."REGULATOR_PERMISSIONS" ORDER BY issued_at DESC'
        return self.execute_and_fetch(sql)

    # --- Documents ---
    def save_document(self, doc_id, doc_type: str, payload: dict) -> bool:
        sql = 'INSERT INTO public."MEDICAL_DOCUMENTS" (doc_id, doc_type, payload) VALUES (%s,%s,%s::jsonb)'
        return self.execute(sql, (str(doc_id), doc_type, json.dumps(payload)))

    def save_document_ledger_meta(self, doc_id, vc_type: str, schema_id: Optional[str], cred_def_id: Optional[str]) -> bool:
        sql = 'INSERT INTO public."DOCUMENT_LEDGER_META" (doc_id, vc_type, schema_id, cred_def_id) VALUES (%s,%s,%s,%s)'
        return self.execute(sql, (str(doc_id), vc_type, schema_id, cred_def_id))
