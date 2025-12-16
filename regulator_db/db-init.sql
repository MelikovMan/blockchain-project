-- Создание базы данных для регулятора
CREATE DATABASE regulator_db;
\c regulator_db;

-- Создание расширения для UUID
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Таблица типов медицинских учреждений (справочник)
CREATE TABLE institution_types (
    type_id VARCHAR(50) PRIMARY KEY,
    description VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблица статусов учреждений (справочник)
CREATE TABLE institution_statuses (
    status_id VARCHAR(50) PRIMARY KEY,
    description VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблица статусов заявок (справочник)
CREATE TABLE request_statuses (
    status_id VARCHAR(50) PRIMARY KEY,
    description VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблица разрешенных типов медицинских документов (справочник)
CREATE TABLE approved_credential_types (
    type_id VARCHAR(50) PRIMARY KEY,
    description VARCHAR(255) NOT NULL,
    version VARCHAR(20) DEFAULT '1.0',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблица зарегистрированных медицинских учреждений
CREATE TABLE institutions (
    institution_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    license_number VARCHAR(100) UNIQUE NOT NULL,
    type_id VARCHAR(50) REFERENCES institution_types(type_id),
    did VARCHAR(255) UNIQUE NOT NULL,
    verkey VARCHAR(255),
    address TEXT,
    contact_email VARCHAR(255),
    status_id VARCHAR(50) REFERENCES institution_statuses(status_id) DEFAULT 'ACTIVE',
    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    suspension_reason TEXT,
    suspended_at TIMESTAMP,
    connection_id VARCHAR(255),
    metadata JSONB DEFAULT '{}'::jsonb,
    
    CONSTRAINT valid_did_format CHECK (did LIKE 'did:sov:%')
);

-- Таблица разрешенных типов документов для учреждения (связь многие-ко-многим)
CREATE TABLE institution_allowed_credentials (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    institution_id UUID REFERENCES institutions(institution_id) ON DELETE CASCADE,
    credential_type_id VARCHAR(50) REFERENCES approved_credential_types(type_id),
    granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    granted_by VARCHAR(255) DEFAULT 'REGULATOR',
    is_active BOOLEAN DEFAULT TRUE,
    
    UNIQUE(institution_id, credential_type_id)
);

-- Таблица заявок на выпуск верифицируемых документов
CREATE TABLE credential_issuance_requests (
    request_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    institution_id UUID REFERENCES institutions(institution_id),
    credential_type_id VARCHAR(50) REFERENCES approved_credential_types(type_id),
    schema_name VARCHAR(255) NOT NULL,
    schema_version VARCHAR(20) DEFAULT '1.0',
    schema_attributes JSONB NOT NULL,
    status_id VARCHAR(50) REFERENCES request_statuses(status_id) DEFAULT 'pending',
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    decision_date TIMESTAMP,
    decision_reason TEXT,
    decision_by VARCHAR(255),
    reviewed_by VARCHAR(255),
    
    CONSTRAINT valid_schema_attributes CHECK (schema_attributes::text ~ '^\[.*\]$')
);

-- Таблица запросов на изменение типов документов
CREATE TABLE credential_modification_requests (
    modification_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    institution_id UUID REFERENCES institutions(institution_id),
    action VARCHAR(10) NOT NULL CHECK (action IN ('ADD', 'REMOVE')),
    status_id VARCHAR(50) REFERENCES request_statuses(status_id) DEFAULT 'pending',
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    decision_date TIMESTAMP,
    decision_reason TEXT,
    decision_by VARCHAR(255),
    
    CONSTRAINT valid_action CHECK (action IN ('ADD', 'REMOVE'))
);

-- Таблица типов документов в запросе на изменение (связь многие-ко-многим)
CREATE TABLE modification_request_credentials (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    modification_id UUID REFERENCES credential_modification_requests(modification_id) ON DELETE CASCADE,
    credential_type_id VARCHAR(50) REFERENCES approved_credential_types(type_id),
    requested_action VARCHAR(10) CHECK (requested_action IN ('ADD', 'REMOVE')),
    
    UNIQUE(modification_id, credential_type_id, requested_action)
);

-- Таблица для хранения соединений регулятора с учреждениями
CREATE TABLE regulator_connections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    hospital_did VARCHAR(255) NOT NULL,
    connection_id VARCHAR(255) NOT NULL,
    their_label VARCHAR(255),
    state VARCHAR(50) DEFAULT 'init',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    
    UNIQUE(hospital_did, connection_id)
);

-- Таблица транзакций эндоузинга
CREATE TABLE endorsement_transactions (
    transaction_id VARCHAR(255) PRIMARY KEY,
    institution_id UUID REFERENCES institutions(institution_id),
    transaction_type VARCHAR(50) NOT NULL,
    transaction_data JSONB NOT NULL,
    state VARCHAR(50) DEFAULT 'request-received',
    requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    endorsed_at TIMESTAMP,
    endorsed_by VARCHAR(255),
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Таблица логов действий регулятора
CREATE TABLE regulator_audit_log (
    log_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    action_type VARCHAR(100) NOT NULL,
    performed_by VARCHAR(255) NOT NULL,
    target_institution_id UUID REFERENCES institutions(institution_id),
    target_request_id UUID,
    description TEXT NOT NULL,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблица отправленных уведомлений
CREATE TABLE sent_notifications (
    notification_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    institution_id UUID REFERENCES institutions(institution_id),
    connection_id VARCHAR(255),
    notification_type VARCHAR(100) NOT NULL,
    message_data JSONB NOT NULL,
    status VARCHAR(50) DEFAULT 'sent',
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    delivered_at TIMESTAMP,
    error_message TEXT,
    
    CONSTRAINT valid_status CHECK (status IN ('sent', 'delivered', 'failed'))
);

-- Таблица принятых сообщений от учреждений
CREATE TABLE received_messages (
    message_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    institution_id UUID REFERENCES institutions(institution_id),
    connection_id VARCHAR(255) NOT NULL,
    message_type VARCHAR(100) NOT NULL,
    message_data JSONB NOT NULL,
    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP,
    processing_status VARCHAR(50) DEFAULT 'received',
    
    CONSTRAINT valid_processing_status CHECK (processing_status IN ('received', 'processing', 'processed', 'error'))
);

-- Индексы для ускорения запросов
CREATE INDEX idx_institutions_did ON institutions(did);
CREATE INDEX idx_institutions_status ON institutions(status_id);
CREATE INDEX idx_institutions_license ON institutions(license_number);
CREATE INDEX idx_institution_allowed_credentials_institution ON institution_allowed_credentials(institution_id);
CREATE INDEX idx_institution_allowed_credentials_type ON institution_allowed_credentials(credential_type_id);
CREATE INDEX idx_credential_issuance_requests_institution ON credential_issuance_requests(institution_id);
CREATE INDEX idx_credential_issuance_requests_status ON credential_issuance_requests(status_id);
CREATE INDEX idx_credential_modification_requests_institution ON credential_modification_requests(institution_id);
CREATE INDEX idx_credential_modification_requests_status ON credential_modification_requests(status_id);
CREATE INDEX idx_regulator_connections_did ON regulator_connections(hospital_did);
CREATE INDEX idx_regulator_connections_active ON regulator_connections(is_active);
CREATE INDEX idx_endorsement_transactions_institution ON endorsement_transactions(institution_id);
CREATE INDEX idx_endorsement_transactions_state ON endorsement_transactions(state);
CREATE INDEX idx_audit_log_institution ON regulator_audit_log(target_institution_id);
CREATE INDEX idx_audit_log_created_at ON regulator_audit_log(created_at DESC);
CREATE INDEX idx_sent_notifications_institution ON sent_notifications(institution_id);
CREATE INDEX idx_sent_notifications_type ON sent_notifications(notification_type);
CREATE INDEX idx_received_messages_institution ON received_messages(institution_id);
CREATE INDEX idx_received_messages_type ON received_messages(message_type);

-- Триггеры для обновления временных меток
CREATE OR REPLACE FUNCTION update_last_updated_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_updated = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_institutions_last_updated 
    BEFORE UPDATE ON institutions 
    FOR EACH ROW 
    EXECUTE FUNCTION update_last_updated_column();

CREATE TRIGGER update_regulator_connections_last_updated 
    BEFORE UPDATE ON regulator_connections 
    FOR EACH ROW 
    EXECUTE FUNCTION update_last_updated_column();

-- Триггер для обновления updated_at в approved_credential_types
CREATE OR REPLACE FUNCTION update_credential_types_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_approved_credential_types_updated_at 
    BEFORE UPDATE ON approved_credential_types 
    FOR EACH ROW 
    EXECUTE FUNCTION update_credential_types_updated_at();

-- Триггер для автоматической записи в аудит-лог при изменении статуса учреждения
CREATE OR REPLACE FUNCTION log_institution_status_change()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.status_id != NEW.status_id THEN
        INSERT INTO regulator_audit_log (
            action_type, 
            performed_by, 
            target_institution_id, 
            description
        ) VALUES (
            'INSTITUTION_STATUS_CHANGE',
            COALESCE(NEW.metadata->>'updated_by', 'SYSTEM'),
            NEW.institution_id,
            'Изменение статуса учреждения с ' || OLD.status_id || ' на ' || NEW.status_id
        );
    END IF;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER log_institution_status_change_trigger
    AFTER UPDATE ON institutions
    FOR EACH ROW
    EXECUTE FUNCTION log_institution_status_change();

-- Вставка справочных данных
INSERT INTO institution_types (type_id, description) VALUES
    ('HOSPITAL', 'Больница'),
    ('POLYCLINIC', 'Поликлиника'),
    ('DIAGNOSTIC_CENTER', 'Диагностический центр'),
    ('LABORATORY', 'Лаборатория'),
    ('PHARMACY', 'Аптека'),
    ('AMBULANCE', 'Скорая помощь'),
    ('RESEARCH_INSTITUTE', 'Научно-исследовательский институт');

INSERT INTO institution_statuses (status_id, description) VALUES
    ('ACTIVE', 'Активно'),
    ('SUSPENDED', 'Приостановлено'),
    ('REVOKED', 'Отозвано'),
    ('PENDING', 'Ожидает активации'),
    ('INACTIVE', 'Неактивно');

INSERT INTO request_statuses (status_id, description) VALUES
    ('pending', 'На рассмотрении'),
    ('approved', 'Одобрено'),
    ('rejected', 'Отклонено'),
    ('cancelled', 'Отменено'),
    ('expired', 'Истек срок');

INSERT INTO approved_credential_types (type_id, description) VALUES
    ('MEDICAL_RECORD', 'Медицинская карта'),
    ('PRESCRIPTION', 'Рецепт'),
    ('LAB_RESULT', 'Результат анализа'),
    ('VACCINATION_CERTIFICATE', 'Сертификат вакцинации'),
    ('DISCHARGE_SUMMARY', 'Выписка из стационара'),
    ('REFERRAL', 'Направление на консультацию'),
    ('SICK_LEAVE_CERTIFICATE', 'Больничный лист'),
    ('MEDICAL_EXAMINATION', 'Заключение медицинского осмотра'),
    ('TREATMENT_PLAN', 'План лечения'),
    ('PROGRESS_NOTE', 'Запись о ходе лечения'),
    ('ALLERGY_LIST', 'Список аллергий'),
    ('MEDICATION_LIST', 'Список принимаемых лекарств'),
    ('IMMUNIZATION_RECORD', 'Карта прививок');

-- Создание представлений для удобства запросов

-- Представление для получения полной информации об учреждениях
CREATE VIEW institutions_full_view AS
SELECT 
    i.institution_id,
    i.name,
    i.license_number,
    i.type_id,
    it.description as institution_type,
    i.did,
    i.verkey,
    i.address,
    i.contact_email,
    i.status_id,
    is2.description as status_description,
    i.registered_at,
    i.last_updated,
    i.suspension_reason,
    i.suspended_at,
    i.connection_id,
    COALESCE(
        (SELECT json_agg(json_build_object('type_id', act.type_id, 'description', act.description))
         FROM institution_allowed_credentials iac
         JOIN approved_credential_types act ON iac.credential_type_id = act.type_id
         WHERE iac.institution_id = i.institution_id AND iac.is_active = TRUE),
        '[]'::json
    ) as allowed_credentials,
    (SELECT COUNT(*) FROM credential_issuance_requests cir 
     WHERE cir.institution_id = i.institution_id AND cir.status_id = 'pending') as pending_requests_count
FROM institutions i
JOIN institution_types it ON i.type_id = it.type_id
JOIN institution_statuses is2 ON i.status_id = is2.status_id;

-- Представление для заявок на выпуск с детальной информацией
CREATE VIEW credential_issuance_requests_view AS
SELECT 
    cir.request_id,
    cir.institution_id,
    i.name as institution_name,
    i.did as institution_did,
    cir.credential_type_id,
    act.description as credential_type_description,
    cir.schema_name,
    cir.schema_version,
    cir.schema_attributes,
    cir.status_id,
    rs.description as status_description,
    cir.submitted_at,
    cir.decision_date,
    cir.decision_reason,
    cir.decision_by,
    cir.reviewed_by,
    CASE 
        WHEN cir.status_id = 'pending' AND cir.submitted_at < NOW() - INTERVAL '30 days' 
        THEN 'OVERDUE'
        ELSE 'ON_TIME'
    END as review_status
FROM credential_issuance_requests cir
JOIN institutions i ON cir.institution_id = i.institution_id
JOIN approved_credential_types act ON cir.credential_type_id = act.type_id
JOIN request_statuses rs ON cir.status_id = rs.status_id;

-- Представление для запросов на изменение с детальной информацией
CREATE VIEW credential_modification_requests_view AS
SELECT 
    cmr.modification_id,
    cmr.institution_id,
    i.name as institution_name,
    i.did as institution_did,
    cmr.action,
    cmr.status_id,
    rs.description as status_description,
    cmr.submitted_at,
    cmr.decision_date,
    cmr.decision_reason,
    cmr.decision_by,
    COALESCE(
        (SELECT json_agg(json_build_object('type_id', act.type_id, 'description', act.description, 'action', mrc.requested_action))
         FROM modification_request_credentials mrc
         JOIN approved_credential_types act ON mrc.credential_type_id = act.type_id
         WHERE mrc.modification_id = cmr.modification_id),
        '[]'::json
    ) as requested_changes
FROM credential_modification_requests cmr
JOIN institutions i ON cmr.institution_id = i.institution_id
JOIN request_statuses rs ON cmr.status_id = rs.status_id;

-- Представление для статистики регулятора
CREATE VIEW regulator_statistics AS
SELECT 
    (SELECT COUNT(*) FROM institutions WHERE status_id = 'ACTIVE') as active_institutions,
    (SELECT COUNT(*) FROM institutions WHERE status_id = 'SUSPENDED') as suspended_institutions,
    (SELECT COUNT(DISTINCT institution_id) FROM institution_allowed_credentials WHERE is_active = TRUE) as institutions_with_credentials,
    (SELECT COUNT(*) FROM credential_issuance_requests WHERE status_id = 'pending') as pending_issuance_requests,
    (SELECT COUNT(*) FROM credential_modification_requests WHERE status_id = 'pending') as pending_modification_requests,
    (SELECT COUNT(*) FROM regulator_connections WHERE is_active = TRUE) as active_connections,
    (SELECT COUNT(DISTINCT credential_type_id) FROM approved_credential_types WHERE is_active = TRUE) as approved_credential_types_count;

-- Создание пользователя для приложения
CREATE USER regulator_app WITH PASSWORD 'secure_password_123';
GRANT CONNECT ON DATABASE regulator_db TO regulator_app;
GRANT USAGE ON SCHEMA public TO regulator_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO regulator_app;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO regulator_app;

-- Комментарии к таблицам для документации
COMMENT ON TABLE institutions IS 'Зарегистрированные медицинские учреждения';
COMMENT ON TABLE institution_allowed_credentials IS 'Разрешенные типы документов для учреждений';
COMMENT ON TABLE credential_issuance_requests IS 'Заявки на выпуск верифицируемых документов';
COMMENT ON TABLE credential_modification_requests IS 'Запросы на изменение типов документов';
COMMENT ON TABLE regulator_connections IS 'Активные соединения с учреждениями';
COMMENT ON TABLE regulator_audit_log IS 'Журнал аудита действий регулятора';
COMMENT ON TABLE sent_notifications IS 'Отправленные уведомления учреждениям';

-- Создание резервной копии структуры базы данных
\echo 'База данных регулятора успешно инициализирована.'
\echo 'Подключение к базе: psql -U regulator_app -d regulator_db'
\echo 'Пароль пользователя: secure_password_123'