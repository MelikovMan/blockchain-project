# db_regulator.py
import os
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from psycopg2.pool import SimpleConnectionPool
from contextlib import contextmanager
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
import json

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация базы данных
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'port': os.environ.get('DB_PORT', '5433'),
    'database': os.environ.get('DB_NAME', 'regulator_db'),
    'user': os.environ.get('DB_USER', 'regulator_app'),
    'password': os.environ.get('DB_PASSWORD', 'secure_password_123'),
    'minconn': 1,
    'maxconn': 10
}

# Пул соединений
connection_pool = None

def init_db_pool():
    """Инициализация пула соединений с БД"""
    global connection_pool
    try:
        connection_pool = SimpleConnectionPool(
            DB_CONFIG['minconn'],
            DB_CONFIG['maxconn'],
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port'],
            database=DB_CONFIG['database'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            cursor_factory=RealDictCursor
        )
        logger.info("Пул соединений с БД инициализирован")
        return True
    except Exception as e:
        logger.error(f"Ошибка инициализации пула соединений: {e}")
        return False

@contextmanager
def get_db_connection():
    """Контекстный менеджер для получения соединения с БД"""
    conn = None
    try:
        if connection_pool is None:
            init_db_pool()
        
        conn = connection_pool.getconn()
        yield conn
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Ошибка работы с БД: {e}")
        raise
    finally:
        if conn:
            connection_pool.putconn(conn)

@contextmanager
def get_db_cursor():
    """Контекстный менеджер для получения курсора БД"""
    with get_db_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            yield cursor
        finally:
            cursor.close()

class RegulatorDatabase:
    """Класс для работы с базой данных регулятора"""
    
    # Методы для работы с учреждениями
    
    @staticmethod
    def get_institution_by_id(institution_id: str) -> Optional[Dict]:
        """Получение учреждения по ID"""
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM institutions_full_view 
                WHERE institution_id = %s
            """, (institution_id,))
            return cursor.fetchone()
    
    @staticmethod
    def get_institution_by_did(did: str) -> Optional[Dict]:
        """Получение учреждения по DID"""
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM institutions_full_view 
                WHERE did = %s
            """, (did,))
            return cursor.fetchone()
    
    @staticmethod
    def get_all_institutions(active_only: bool = True) -> List[Dict]:
        """Получение всех учреждений"""
        with get_db_cursor() as cursor:
            if active_only:
                cursor.execute("""
                    SELECT * FROM institutions_full_view 
                    WHERE status_id = 'ACTIVE'
                    ORDER BY name
                """)
            else:
                cursor.execute("""
                    SELECT * FROM institutions_full_view 
                    ORDER BY name
                """)
            return cursor.fetchall()
    
    @staticmethod
    def create_institution(institution_data: Dict) -> Optional[Dict]:
        """Создание нового учреждения"""
        with get_db_cursor() as cursor:
            cursor.execute("""
                INSERT INTO institutions (
                    name, license_number, type_id, did, verkey, 
                    address, contact_email, status_id, metadata
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s
                ) RETURNING *
            """, (
                institution_data['name'],
                institution_data['license_number'],
                institution_data.get('type_id', 'HOSPITAL'),
                institution_data['did'],
                institution_data.get('verkey'),
                institution_data.get('address'),
                institution_data.get('contact_email'),
                institution_data.get('status_id', 'ACTIVE'),
                Json(institution_data.get('metadata', {}))
            ))
            return cursor.fetchone()
    
    @staticmethod
    def update_institution_status(institution_id: str, status_id: str, 
                                 reason: str = None, updated_by: str = 'SYSTEM') -> bool:
        """Обновление статуса учреждения"""
        with get_db_cursor() as cursor:
            cursor.execute("""
                UPDATE institutions 
                SET status_id = %s, 
                    suspension_reason = %s,
                    suspended_at = CASE 
                        WHEN %s = 'SUSPENDED' THEN CURRENT_TIMESTAMP 
                        ELSE NULL 
                    END,
                    metadata = jsonb_set(
                        COALESCE(metadata, '{}'::jsonb), 
                        '{updated_by}', 
                        to_jsonb(%s::text)
                    )
                WHERE institution_id = %s
                RETURNING institution_id
            """, (status_id, reason, status_id, updated_by, institution_id))
            return cursor.fetchone() is not None
    
    @staticmethod
    def update_institution_connection(institution_id: str, connection_id: str) -> bool:
        """Обновление connection_id учреждения"""
        with get_db_cursor() as cursor:
            cursor.execute("""
                UPDATE institutions 
                SET connection_id = %s,
                    last_updated = CURRENT_TIMESTAMP
                WHERE institution_id = %s
                RETURNING institution_id
            """, (connection_id, institution_id))
            return cursor.fetchone() is not None
    
    # Методы для работы с разрешенными типами документов
    
    @staticmethod
    def add_allowed_credential(institution_id: str, credential_type_id: str, 
                              granted_by: str = 'REGULATOR') -> bool:
        """Добавление разрешенного типа документа учреждению"""
        with get_db_cursor() as cursor:
            cursor.execute("""
                INSERT INTO institution_allowed_credentials 
                    (institution_id, credential_type_id, granted_by)
                VALUES (%s, %s, %s)
                ON CONFLICT (institution_id, credential_type_id) 
                DO UPDATE SET is_active = TRUE,
                            granted_at = CURRENT_TIMESTAMP,
                            granted_by = EXCLUDED.granted_by
                RETURNING id
            """, (institution_id, credential_type_id, granted_by))
            return cursor.fetchone() is not None
    
    @staticmethod
    def remove_allowed_credential(institution_id: str, credential_type_id: str) -> bool:
        """Удаление разрешенного типа документа у учреждения"""
        with get_db_cursor() as cursor:
            cursor.execute("""
                UPDATE institution_allowed_credentials 
                SET is_active = FALSE 
                WHERE institution_id = %s 
                  AND credential_type_id = %s
                  AND is_active = TRUE
                RETURNING id
            """, (institution_id, credential_type_id))
            return cursor.fetchone() is not None
    
    @staticmethod
    def get_allowed_credentials(institution_id: str) -> List[str]:
        """Получение списка разрешенных типов документов учреждения"""
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT credential_type_id 
                FROM institution_allowed_credentials 
                WHERE institution_id = %s AND is_active = TRUE
            """, (institution_id,))
            return [row['credential_type_id'] for row in cursor.fetchall()]
    
    @staticmethod
    def has_credential_permission(institution_id: str, credential_type_id: str) -> bool:
        """Проверка, имеет ли учреждение право выпускать тип документа"""
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT id 
                FROM institution_allowed_credentials 
                WHERE institution_id = %s 
                  AND credential_type_id = %s 
                  AND is_active = TRUE
            """, (institution_id, credential_type_id))
            return cursor.fetchone() is not None
    
    # Методы для работы с заявками на выпуск VC
    
    @staticmethod
    def create_credential_issuance_request(request_data: Dict) -> Optional[Dict]:
        """Создание заявки на выпуск VC"""
        with get_db_cursor() as cursor:
            cursor.execute("""
                INSERT INTO credential_issuance_requests (
                    institution_id, credential_type_id, schema_name, 
                    schema_version, schema_attributes, status_id
                ) VALUES (
                    %s, %s, %s, %s, %s, %s
                ) RETURNING *
            """, (
                request_data['institution_id'],
                request_data['credential_type_id'],
                request_data.get('schema_name', 'Unknown'),
                request_data.get('schema_version', '1.0'),
                Json(request_data['schema_attributes']),
                request_data.get('status_id', 'pending')
            ))
            return cursor.fetchone()
    
    @staticmethod
    def get_credential_issuance_request(request_id: str) -> Optional[Dict]:
        """Получение заявки на выпуск VC по ID"""
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM credential_issuance_requests_view 
                WHERE request_id = %s
            """, (request_id,))
            return cursor.fetchone()
    
    @staticmethod
    def get_pending_credential_issuance_requests() -> List[Dict]:
        """Получение всех незавершенных заявок"""
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM credential_issuance_requests_view 
                WHERE status_id = 'pending'
                ORDER BY submitted_at
            """)
            return cursor.fetchall()
    
    @staticmethod
    def update_credential_issuance_request_status(
        request_id: str, 
        status_id: str, 
        decision_reason: str = None,
        decision_by: str = 'REGULATOR'
    ) -> bool:
        """Обновление статуса заявки на выпуск VC"""
        with get_db_cursor() as cursor:
            cursor.execute("""
                UPDATE credential_issuance_requests 
                SET status_id = %s,
                    decision_date = CURRENT_TIMESTAMP,
                    decision_reason = %s,
                    decision_by = %s
                WHERE request_id = %s
                RETURNING request_id
            """, (status_id, decision_reason, decision_by, request_id))
            return cursor.fetchone() is not None
    
    # Методы для работы с запросами на изменение VC
    
    @staticmethod
    def create_credential_modification_request(request_data: Dict) -> Optional[Dict]:
        """Создание запроса на изменение типов VC"""
        with get_db_cursor() as cursor:
            cursor.execute("""
                INSERT INTO credential_modification_requests (
                    institution_id, action, status_id
                ) VALUES (%s, %s, %s)
                RETURNING *
            """, (
                request_data['institution_id'],
                request_data['action'],
                request_data.get('status_id', 'pending')
            ))
            
            result = cursor.fetchone()
            
            # Добавляем типы документов в запрос
            for credential_type in request_data['credential_types']:
                cursor.execute("""
                    INSERT INTO modification_request_credentials 
                        (modification_id, credential_type_id, requested_action)
                    VALUES (%s, %s, %s)
                """, (result['modification_id'], credential_type, request_data['action']))
            
            return result
    
    @staticmethod
    def get_credential_modification_request(modification_id: str) -> Optional[Dict]:
        """Получение запроса на изменение по ID"""
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM credential_modification_requests_view 
                WHERE modification_id = %s
            """, (modification_id,))
            return cursor.fetchone()
    
    @staticmethod
    def update_credential_modification_request_status(
        modification_id: str, 
        status_id: str, 
        decision_reason: str = None,
        decision_by: str = 'REGULATOR'
    ) -> bool:
        """Обновление статуса запроса на изменение VC"""
        with get_db_cursor() as cursor:
            cursor.execute("""
                UPDATE credential_modification_requests 
                SET status_id = %s,
                    decision_date = CURRENT_TIMESTAMP,
                    decision_reason = %s,
                    decision_by = %s
                WHERE modification_id = %s
                RETURNING modification_id
            """, (status_id, decision_reason, decision_by, modification_id))
            return cursor.fetchone() is not None
    
    # Методы для работы с соединениями
    
    @staticmethod
    def save_connection(hospital_did: str, connection_id: str, their_label: str = None) -> bool:
        """Сохранение соединения с учреждением"""
        with get_db_cursor() as cursor:
            cursor.execute("""
                INSERT INTO regulator_connections 
                    (hospital_did, connection_id, their_label, state, is_active)
                VALUES (%s, %s, %s, 'active', TRUE)
                ON CONFLICT (hospital_did, connection_id) 
                DO UPDATE SET 
                    their_label = EXCLUDED.their_label,
                    state = 'active',
                    is_active = TRUE,
                    last_updated = CURRENT_TIMESTAMP
                RETURNING id
            """, (hospital_did, connection_id, their_label))
            return cursor.fetchone() is not None
    
    @staticmethod
    def get_connection_by_did(hospital_did: str) -> Optional[Dict]:
        """Получение активного соединения по DID учреждения"""
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM regulator_connections 
                WHERE hospital_did = %s AND is_active = TRUE
                ORDER BY last_updated DESC 
                LIMIT 1
            """, (hospital_did,))
            return cursor.fetchone()
    
    @staticmethod
    def deactivate_connection(connection_id: str) -> bool:
        """Деактивация соединения"""
        with get_db_cursor() as cursor:
            cursor.execute("""
                UPDATE regulator_connections 
                SET is_active = FALSE,
                    state = 'inactive',
                    last_updated = CURRENT_TIMESTAMP
                WHERE connection_id = %s
                RETURNING id
            """, (connection_id,))
            return cursor.fetchone() is not None
    
    # Методы для работы с уведомлениями
    
    @staticmethod
    def save_notification(notification_data: Dict) -> Optional[Dict]:
        """Сохранение отправленного уведомления"""
        with get_db_cursor() as cursor:
            cursor.execute("""
                INSERT INTO sent_notifications (
                    institution_id, connection_id, notification_type, 
                    message_data, status, sent_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s
                ) RETURNING *
            """, (
                notification_data.get('institution_id'),
                notification_data.get('connection_id'),
                notification_data['notification_type'],
                Json(notification_data['message_data']),
                notification_data.get('status', 'sent'),
                notification_data.get('sent_at', datetime.now())
            ))
            return cursor.fetchone()
    
    @staticmethod
    def update_notification_status(notification_id: str, status: str, 
                                  error_message: str = None) -> bool:
        """Обновление статуса уведомления"""
        with get_db_cursor() as cursor:
            cursor.execute("""
                UPDATE sent_notifications 
                SET status = %s,
                    error_message = %s,
                    delivered_at = CASE 
                        WHEN %s = 'delivered' THEN CURRENT_TIMESTAMP 
                        ELSE delivered_at 
                    END
                WHERE notification_id = %s
                RETURNING notification_id
            """, (status, error_message, status, notification_id))
            return cursor.fetchone() is not None
    
    # Методы для аудит-лога
    
    @staticmethod
    def log_action(action_data: Dict) -> Optional[Dict]:
        """Запись действия в аудит-лог"""
        with get_db_cursor() as cursor:
            cursor.execute("""
                INSERT INTO regulator_audit_log (
                    action_type, performed_by, target_institution_id,
                    target_request_id, description, ip_address, user_agent
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s
                ) RETURNING *
            """, (
                action_data['action_type'],
                action_data['performed_by'],
                action_data.get('target_institution_id'),
                action_data.get('target_request_id'),
                action_data['description'],
                action_data.get('ip_address'),
                action_data.get('user_agent')
            ))
            return cursor.fetchone()
    
    # Методы для статистики
    
    @staticmethod
    def get_statistics() -> Dict:
        """Получение статистики регулятора"""
        with get_db_cursor() as cursor:
            cursor.execute("SELECT * FROM regulator_statistics")
            stats = cursor.fetchone()
            
            # Дополнительная статистика
            cursor.execute("""
                SELECT 
                    (SELECT COUNT(*) FROM credential_issuance_requests 
                     WHERE status_id = 'approved' 
                     AND submitted_at >= CURRENT_DATE - INTERVAL '30 days') as approved_last_30_days,
                    (SELECT COUNT(*) FROM credential_modification_requests 
                     WHERE status_id = 'approved' 
                     AND submitted_at >= CURRENT_DATE - INTERVAL '30 days') as modifications_last_30_days,
                    (SELECT COUNT(DISTINCT institution_id) FROM sent_notifications 
                     WHERE sent_at >= CURRENT_DATE - INTERVAL '7 days') as notified_institutions_7_days
            """)
            additional_stats = cursor.fetchone()
            
            return {**stats, **additional_stats}
    
    @staticmethod
    def get_recent_activity(limit: int = 50) -> List[Dict]:
        """Получение последних действий"""
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT 
                    al.action_type,
                    al.performed_by,
                    al.description,
                    al.created_at,
                    i.name as institution_name,
                    i.did as institution_did
                FROM regulator_audit_log al
                LEFT JOIN institutions i ON al.target_institution_id = i.institution_id
                ORDER BY al.created_at DESC
                LIMIT %s
            """, (limit,))
            return cursor.fetchall()
    
    # Вспомогательные методы
    
    @staticmethod
    def check_credential_type_exists(credential_type_id: str) -> bool:
        """Проверка существования типа документа"""
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT type_id FROM approved_credential_types 
                WHERE type_id = %s AND is_active = TRUE
            """, (credential_type_id,))
            return cursor.fetchone() is not None
    
    @staticmethod
    def get_all_approved_credential_types() -> List[Dict]:
        """Получение всех разрешенных типов документов"""
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM approved_credential_types 
                WHERE is_active = TRUE
                ORDER BY description
            """)
            return cursor.fetchall()

# Утилитарные функции для миграции данных

def migrate_from_dicts_to_db():
    """Миграция данных из словарей в базу данных"""
    try:
        # Инициализация пула соединений
        init_db_pool()
        
        logger.info("Начало миграции данных из словарей в БД...")
        
        # Здесь будут функции миграции существующих данных
        # Пример для миграции учреждений из REGISTERED_INSTITUTIONS
        
        migration_success = True
        
        logger.info("Миграция данных завершена успешно")
        return migration_success
        
    except Exception as e:
        logger.error(f"Ошибка при миграции данных: {e}")
        return False

# Функция для проверки соединения с БД
def test_db_connection():
    """Тестирование соединения с базой данных"""
    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT 1 as test")
            result = cursor.fetchone()
            logger.info(f"Соединение с БД успешно. Результат теста: {result}")
            return True
    except Exception as e:
        logger.error(f"Ошибка соединения с БД: {e}")
        return False

# Инициализация при импорте
init_db_pool()