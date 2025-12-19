import os
import sqlite3
from typing import Optional, Dict, Any

def drop_table(db_name: str = "Hospital.db") -> sqlite3.Connection:
    try:
        # Проверяем, существует ли файл базы данных
        db_exists = os.path.exists(db_name)

        # Создаем соединение с базой данных
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()


        # Уничтожаем таблицу Metadata (Метаданные)
        cursor.execute('''
        DROP TABLE IF EXISTS Metadata 
        ''')

        # Уничтожаем таблицу UZI (УЗИ исследования)
        cursor.execute('''
        DROP TABLE IF EXISTS UZI 
        ''')

        conn.commit()



        print("Таблицы удалены")

        return conn

    except sqlite3.Error as e:
        print(f"Ошибка при удалении таблиц: {e}")
    raise
def create_database(db_name: str = "Hospital.db") -> sqlite3.Connection:
    """

    Создает
    базу
    данных
    SQLite
    с
    таблицами
    UZI
    и
    Metadata

    Args:
    db_name: Имя
    файла
    базы
    данных


    Returns:
    sqlite3.Connection: Объект
    соединения
    с
    базой
    данных
    """
    try:
        # Проверяем, существует ли файл базы данных
        db_exists = os.path.exists(db_name)

        # Создаем соединение с базой данных
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()

        # Включаем поддержку внешних ключей
        cursor.execute('''
        PRAGMA foreign_keys = ON;''')

        # Создаем таблицу Metadata (Метаданные)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS Metadata (
            hospital_did INTEGER ,
            hospital_name VARCHAR(100) NOT NULL,
            hospital_endpoint VARCHAR,
            vc_type INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (hospital_did, vc_type)
        )
        ''')

        # Создаем таблицу UZI (УЗИ исследования)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS UZI (
            vc INTEGER PRIMARY KEY,
            data_isl TIMESTAMP NOT NULL,
            number_protocol INTEGER UNIQUE NOT NULL,
            FIO VARCHAR(100) NOT NULL,
            gender VARCHAR(1) CHECK(gender IN ('М', 'Ж', 'M', 'F')),
            date_birth TIMESTAMP,
            number_med_card INTEGER,
            napr_otd VARCHAR(500),
            vid_issled VARCHAR(200),
            vc_type INTEGER,
            scaner VARCHAR(100),
            datchik VARCHAR(100),
            opisanie TEXT,
            zakl TEXT,
            fio_vrach VARCHAR(50),
            hospital_did INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (vc_type, hospital_did) REFERENCES Metadata(vc_type, hospital_did) ON DELETE SET NULL

        )
        ''')

        # Создаем индексы для повышения производительности
        cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_uzi_data_isl 
        ON UZI(data_isl)
        ''')

        cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_uzi_number_protocol 
        ON UZI(number_protocol)
        ''')

        cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_uzi_fio 
        ON UZI(FIO)
        ''')

        cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_uzi_hospital_did 
        ON UZI(hospital_did)
        ''')

        cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_metadata_hospital_name 
        ON Metadata(hospital_name)
        ''')

        conn.commit()

        if db_exists:
            print(f"База данных '{db_name}' успешно подключена")
        else:
            print(f"База данных '{db_name}' успешно создана")

        print("Таблицы созданы:")
        print("1. UZI - таблица ультразвуковых исследований")
        print("2. Metadata - таблица метаданных больниц")

        return conn

    except sqlite3.Error as e:
        print(f"Ошибка при создании базы данных: {e}")
    raise


def insert_sample_data(conn: sqlite3.Connection) -> None:
    """
    Вставляет
    тестовые
    данные
    в
    таблицы

    Args:
    conn: Соединение
    с
    базой
    данных
    """
    try:
        cursor = conn.cursor()

        # Вставляем данные в таблицу Metadata
        metadata_samples = [
            (1, 'Городская клиническая больница №1', 1, 'http://gkb1.ru/api/v1'),
            (1, 'Городская клиническая больница №1', 2, 'http://gkb1.ru/api/v2'),
            (2, 'Центральная районная больница', 2, 'https://crb.local/api2'),
            (2, 'Центральная районная больница', 1, 'https://crb.local/api'),
            (3, 'Диагностический центр "Здоровье"', 2, 'https://diagnostika.zdorovie/api2'),
            (3, 'Диагностический центр "Здоровье"', 1, 'https://diagnostika.zdorovie/api'),
        ]

        for metadata in metadata_samples:
            cursor.execute('''
            INSERT OR REPLACE INTO Metadata (hospital_did, hospital_name, vc_type, hospital_endpoint)
            VALUES (?, ?, ?, ?)
            ''', metadata)

        # Вставляем данные в таблицу UZI
        uzi_samples = [
            (
                1, #vc
                '2024-01-15 14:30:00',  # data_isl
                2024001,  # number_protocol
                'Иванов Иван Иванович',  # FIO
                'М',  # gender
                '1985-07-20 00:00:00',  # date_birth
                123456,  # number_med_card
                'Терапевтическое отделение',  # napr_otd
                'УЗИ органов брюшной полости',  # vid_issled
                1,  # vc_type
                'Siemens Acuson S2000',  # scaner
                'Конвексный 3.5 МГц',  # datchik
                'Пациент в положении лежа на спине. Исследованы печень, желчный пузырь, поджелудочная железа, селезенка, почки. Сканирование выполнено в различных плоскостях.',
                # opisanie
                'Эхографические признаки хронического холецистита. Диффузные изменения поджелудочной железы. Остальные органы без патологии.',
                # zakl
                'Петрова М.С.',  # fio_vrach
                1  # hospital_did
            ),
            (
                2,
                '2024-01-16 10:15:00',
                2024002,
                'Сидорова Анна Петровна',
                'Ж',
                '1992-03-15 00:00:00',
                789012,
                'Гинекологическое отделение',
                'УЗИ органов малого таза',
                2,
                'GE Voluson E8',
                'Вагинальный 5-9 МГц',
                'Трансвагинальное исследование. Определены размеры и структура матки, яичников. Измерен эндометрий.',
                'Матка и яичники без особенностей. Эндометрий соответствует фазе цикла.',
                'Смирнов А.В.',
                2
            ),
            (
                3,
                '2024-01-17 09:00:00',
                2024003,
                'Петров Сергей Николаевич',
                'М',
                '1978-11-30 00:00:00',
                345678,
                'Кардиологическое отделение',
                'Эхокардиография',
                1,
                'Philips EPIQ 7',
                'Секторный 2.5 МГц',
                'Исследование сердца в М-режиме, В-режиме и допплеровском режиме. Измерены размеры камер, толщина стенок, оценена сократительная функция.',
                'Умеренная гипертрофия левого желудочка. Фракция выброса 58%. Клапанный аппарат без особенностей.',
                'Козлова И.П.',
                2
            )
        ]

        for uzi in uzi_samples:
            cursor.execute('''
            INSERT OR REPLACE INTO UZI (
                vc, data_isl, number_protocol, FIO, gender, date_birth,
                number_med_card, napr_otd, vid_issled, vc_type, scaner, datchik,
                opisanie, zakl, fio_vrach, hospital_did
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', uzi)

        conn.commit()
        print("Тестовые данные успешно добавлены")

    except sqlite3.Error as e:
        print(f"Ошибка при вставке тестовых данных: {e}")

def display_sample_data(conn: sqlite3.Connection) -> None:
    """
    Отображает
    примеры
    данных
    из
    таблиц

    Args:
    conn: Соединение
    с
    базой
    данных
    """
    cursor = conn.cursor()

    print("\n" + "="*60)
    print("ПРИМЕРЫ ДАННЫХ")
    print("="*60)

    # Данные из таблицы Metadata
    print("\nТаблица Metadata:")
    print("-" * 40)
    cursor.execute("SELECT * FROM Metadata ORDER BY hospital_did")
    metadata_rows = cursor.fetchall()

    for row in metadata_rows:
        print(f"ID: {row[0]}, Название: {row[1]}")
        print(f"Endpoint: {row[2]}")
        print(f"vc_type: {row[3]}")
        print(f"Создано: {row[4]}, Обновлено: {row[5]}")
        print("-" * 40)

    # Данные из таблицы UZI
    print("\nТаблица UZI (первые 2 записи):")
    print("-" * 40)
    cursor.execute('''
    SELECT *
    FROM UZI u
    LEFT JOIN Metadata m ON u.hospital_did = m.hospital_did
    ORDER BY u.data_isl DESC
    ''')

    uzi_rows = cursor.fetchall()

    for row in uzi_rows:
        print(f"Протокол №: {row[0]}")
        print(f"Пациент: {row[1]}")
        print(f"Дата исследования: {row[2]}")
        print(f"Вид исследования: {row[3]}")
        print(f"Врач: {row[4]}")
        print(f"Больница: {row[5]}")
        print("-" * 40)

class HospitalDBManager:
    """
    Менеджер
    для
    работы
    с
    базой
    данных
    УЗИ
    """

    def __init__(self, db_path: str = "Hospital.db"):
        self.db_path = db_path
        self.conn = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    def connect(self) -> None:
        """
    Подключение
    к
    базе
    данных
    """
        self.conn = create_database(self.db_path)

    def disconnect(self) -> None:
        """
    Отключение
    от
    базы
    данных
    """
        if self.conn:
            self.conn.close()
            print("\nСоединение с базой данных закрыто")

    def add_record(self, base_name, record_data: Dict[str, Any]) -> int:
        """
    Добавляет
    запись
    об
    УЗИ
    исследовании

    Args:
    record_data: Словарь
    с
    данными
    записи

    Returns:
    int: ID
    добавленной
    записи
    """
        try:
            cursor = self.conn.cursor()
            if base_name=="UZI":
                # Подготавливаем данные для вставки
                data = (
                    record_data.get('vc'),
                    record_data.get('data_isl'),
                    record_data.get('number_protocol'),
                    record_data.get('FIO'),
                    record_data.get('gender'),
                    record_data.get('date_birth'),
                    record_data.get('number_med_card'),
                    record_data.get('napr_otd'),
                    record_data.get('vid_issled'),
                    record_data.get('vc_type'),
                    record_data.get('scaner'),
                    record_data.get('datchik'),
                    record_data.get('opisanie'),
                    record_data.get('zakl'),
                    record_data.get('fio_vrach'),
                    record_data.get('hospital_did')
                )

                cursor.execute('''
                INSERT INTO '''+base_name+''' (
                    vc, data_isl, number_protocol, FIO, gender, date_birth,
                    number_med_card, napr_otd, vid_issled, vc_type, scaner, datchik,
                    opisanie, zakl, fio_vrach, hospital_did
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', data)

                record_id = cursor.lastrowid
                self.conn.commit()

                print(f"Запись УЗИ №{record_data.get('number_protocol')} успешно добавлена (ID: {record_id})")
                return record_id

        except sqlite3.IntegrityError as e:
            print(f"Ошибка целостности данных: {e}")
            return -1
        except sqlite3.Error as e:
            print(f"Ошибка при добавлении записи: {e}")
            return -1

    def add_hospital(self, hospital_did : int, name: str, vc_type: int, endpoint: Optional[str] = None) -> int:
        """
        Добавляет
        новую
        больницу
        в
        таблицу
        Metadata

        Args:
        name: Название
        больницы
        endpoint: Endpoint
        API
        больницы

        Returns:
        int: ID
        добавленной
        больницы
        """
        try:
            cursor = self.conn.cursor()

            cursor.execute('''
            INSERT INTO Metadata (hospital_did, hospital_name, vc_type, hospital_endpoint)
            VALUES (?, ?, ?, ?)
            ''', (hospital_did, name, vc_type, endpoint))

            #hospital_did = cursor.lastrowid
            self.conn.commit()

            print(f"Больница '{name}' успешно добавлена (ID: {hospital_did})")
            return hospital_did

        except sqlite3.Error as e:
            print(f"Ошибка при добавлении больницы: {e}")
            return -1

    def search_uzi_by_vc(self, vc: int) -> list:
        """
        Поиск
        исследований
        по
        имени
        пациента

        Args:
        vc: id исследования

        Returns:
        list: Список
        найденных
        записей
        """
        try:
            cursor = self.conn.cursor()

            cursor.execute('''
            SELECT * FROM UZI 
            WHERE vc=?
            ORDER BY data_isl DESC
            ''', (vc,))

            return cursor.fetchall()

        except sqlite3.Error as e:
            print(f"Ошибка при поиске: {e}")
        return []

def main():
    """
    Основная
    функция
    для
    создания
    и
    тестирования
    базы
    данных
    """
    print("СОЗДАНИЕ БАЗЫ ДАННЫХ УЗИ ИССЛЕДОВАНИЙ")
    print("="*50)

    # Создаем и заполняем базу данных
    try:

        conn = drop_table()
        # Создание базы данных
        conn = create_database()

        # Вставка тестовых данных
        insert_sample_data(conn)

        # Показать примеры данных
        display_sample_data(conn)

        # Пример использования менеджера базы данных
        print("\n" + "="*60)
        print("ИСПОЛЬЗОВАНИЕ МЕНЕДЖЕРА БАЗЫ ДАННЫХ")
        print("="*60)

        with HospitalDBManager() as db_manager:
            # Добавляем новую больницу
            new_hospital_did = db_manager.add_hospital(
                hospital_did=4,
                name="Областной диагностический центр",
                vc_type=1,
                endpoint="https://odc.ru/api/Hospital",

            )

            # Добавляем новую запись УЗИ
            new_record = {
                'vc': 4,
                'data_isl': '2024-01-18 11:00:00',
                'number_protocol': 2024004,
                'FIO': 'Смирнова Ольга Васильевна',
                'gender': 'Ж',
                'date_birth': '1988-05-12 00:00:00',
                'number_med_card': 901234,
                'napr_otd': 'Урологическое отделение',
                'vid_issled': 'УЗИ почек и мочевого пузыря',
                'vc_type': 1,
                'scaner': 'Toshiba Aplio 500',
                'datchik': 'Конвексный 3.5 МГц',
                'opisanie': 'Исследование почек в поперечной и продольной плоскостях. Оценка размеров, структуры, наличия конкрементов.',
                'zakl': 'Почки обычных размеров и структуры. Конкрементов не выявлено.',
                'fio_vrach': 'Иванов П.К.',
                'hospital_did': new_hospital_did
            }
            base_name="UZI"

            db_manager.add_record(base_name, new_record)

            # Поиск записей по пациенту
            print("\nПоиск записей по vc:")
            results = db_manager.search_uzi_by_vc(1)
            for result in results:
                print(f"  - {result[3]} (Протокол: {result[2]}, Дата: {result[1]}, vc: {result[0]})")

        print("\n" + "="*60)
        print("БАЗА ДАННЫХ УСПЕШНО СОЗДАНА И ПРОТЕСТИРОВАНА")
        print("="*60)

    except Exception as e:
        print(f"Произошла ошибка: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    # Проверка доступности sqlite3
    print(f"Версия SQLite: {sqlite3.sqlite_version}")
    print(f"Версия модуля SQLite3: {sqlite3.version}")

    # Запуск основной функции
    main()