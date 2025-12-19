import sqlite3

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib import colors
from datetime import datetime
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from DataBase.work_db import HospitalDBManager
import os

# Регистрация шрифта (проверяем наличие файла)
font_path = 'fonts/DejaVuSans.ttf'
if os.path.exists(font_path):
    try:
        pdfmetrics.registerFont(TTFont('DejaVu', font_path))
        FONT_NAME = 'DejaVu'
        print(f"Шрифт DejaVu зарегистрирован из {font_path}")
    except Exception as e:
        print(f"Ошибка загрузки шрифта: {e}")
        print("Используется стандартный шрифт (возможны проблемы с кириллицей)")
        FONT_NAME = 'Helvetica'
else:
    print(f"Файл шрифта не найден: {font_path}")
    print("Используется стандартный шрифт (возможны проблемы с кириллицей)")
    FONT_NAME = 'Helvetica'


def generate_medical_pdf(
        output_file,
        date: str,
        number_protocol: int,
        FIO: str,
        gender: str,
        date_birth: str,
        number_med_cart: int,
        nupr_otdel: str,
        vid_issled: str,
        vc_type: int,
        scaner: str,
        datchik: str,
        opisanie: str,
        zakl: str,
        fio_vrach: str,
        stamp_path=None
):
    doc = SimpleDocTemplate(
        output_file,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()

    # Создаем стили с указанием шрифта
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Title'],
        alignment=TA_CENTER,
        fontName=FONT_NAME,  # Указываем шрифт
        fontSize=14,
        spaceAfter=20
    )

    heading_style = ParagraphStyle(
        'HeadingStyle',
        parent=styles['Heading3'],
        fontName=FONT_NAME,  # Указываем шрифт
        fontSize=12,
        spaceAfter=6
    )

    normal_style = ParagraphStyle(
        'NormalStyle',
        parent=styles['Normal'],
        fontName=FONT_NAME,  # Указываем шрифт
        fontSize=10,
        leading=14
    )

    # Стиль для текста в таблицах
    table_text_style = ParagraphStyle(
        'TableTextStyle',
        parent=styles['Normal'],
        fontName=FONT_NAME,  # Указываем шрифт
        fontSize=10
    )

    story = []

    # Заголовок
    story.append(Paragraph("ПРОТОКОЛ ИССЛЕДОВАНИЯ", title_style))
    story.append(Spacer(1, 20))

    story.append(Spacer(1, 15))

    # Основные данные пациента
    patient_data = [
        [Paragraph("Дата и время исследования:", table_text_style), Paragraph(date, table_text_style)],
        [Paragraph("Номер протокола:", table_text_style), Paragraph(str(number_protocol), table_text_style)],
        [Paragraph("ФИО больного:", table_text_style), Paragraph(FIO, table_text_style)],
        [Paragraph("Пол:", table_text_style), Paragraph(gender, table_text_style)],
        [Paragraph("Дата рождения:", table_text_style), Paragraph(date_birth, table_text_style)],
        [Paragraph("Номер мед. карты:", table_text_style), Paragraph(str(number_med_cart), table_text_style)],
        [Paragraph("Направившее отделение:", table_text_style), Paragraph(nupr_otdel, table_text_style)],
        [Paragraph("Вид исследования:", table_text_style), Paragraph(vid_issled, table_text_style)],
    ]

    table = Table(patient_data, colWidths=[200, 300])
    table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LINEBELOW', (0, 0), (-1, -1), 0.25, colors.grey),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('FONTNAME', (0, 0), (-1, -1), FONT_NAME),  # Указываем шрифт для таблицы
    ]))
    story.append(table)
    story.append(Spacer(1, 20))
    # УЗ-сканер и характеристики датчиков (вне таблицы)
    scanner_text = f"<b>УЗ-сканер:</b> {scaner}, <b>Частотные характеристики датчиков:</b> {datchik}"
    story.append(Paragraph(scanner_text, table_text_style))
    story.append(Spacer(1, 15))

    # Описание процедуры
    opisanie_text = f"<b>Описание процедуры:</b> {opisanie}"
    story.append(Paragraph(opisanie_text, normal_style))
    story.append(Spacer(1, 15))

    # Заключение
    zakl_text = f"<b>Заключение:</b> {zakl}"
    story.append(Paragraph(zakl_text, normal_style))
    story.append(Spacer(1, 50))

    # Подпись врача
    sign_table = Table(
        [
            [
                Paragraph("Врач:", table_text_style),
                Paragraph(fio_vrach, table_text_style),
                Paragraph("Подпись:", table_text_style),
                Paragraph("______________", table_text_style)
            ]
        ],
        colWidths=[60, 200, 80, 120]
    )
    sign_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('TOPPADDING', (0, 0), (-1, -1), 12),
        ('FONTNAME', (0, 0), (-1, -1), FONT_NAME),  # Указываем шрифт для таблицы
    ]))

    story.append(sign_table)
    # Печать на отдельной строке справа
    if stamp_path and os.path.exists(stamp_path):
        story.append(Spacer(1, 10))  # Небольшой отступ

        # Таблица для выравнивания печати по правому краю
        stamp_table = Table([[Image(stamp_path, width=120, height=130)]], colWidths=[515])
        stamp_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),  # Печать справа
        ]))
        story.append(stamp_table)

    doc.build(story)
    print(f"PDF '{output_file}' успешно создан")

def populate_test_data():
    with HospitalDBManager() as db_manager:
        # Добавляем новую больницу
        # раскоментите для добавления больницы и узи
        new_hospital_did = db_manager.add_hospital(
        hospital_did="M2yeapcDR9P7pi7mETjBui",
        name="Областной диагностический центр",
        vc_type=1,
        endpoint="https://odc.ru/api/Hospital",
        )

        new_record = {
            'vc': 4,
            'data_isl': '2024-01-18 11:00:00',
            'number_protocol': 2024004,
            'FIO': 'Смирнова Ольга Васильевна',
            'gender': 'Ж',
            'date_birth': '1988-05-12 00:00:00',
            'number_med_card': 901234,
            'napr_otd': 'Кардиологический центр поликлиники СКАЛ',
            'vid_issled': 'Триплексное сканирование артерий экстракраниального отдела брахиоцефальной системы',
            'vc_type': 1,
            'scaner': 'PHILIPS EPIQ5G',
            'datchik': 'Конвексный 3.5 МГц',
            'opisanie': '''
            1.Стенки артерий неравномерно утолщены (КИМ 1,1-1.3 мм), дифференциация на слои
нарушена.
Паравазальные мягкие ткани не изменены.
2.Диаметры общей, внутренней, наружной сонных, подключичной артерий с обеих сторон и
плече-головного ствола в пределах нормы с обеих сторон.
В бифуркации правой ОСА гетерогенная АСБ стеноз до 50%, в ВСА пролонгированная
гетерогенная АСБ стеноз более 70% (ЛСК до 230-250 см/сек.
В просвете левой ОСА гетерогенная пролонгированная АСБ стеноз до 40%, в бифуркации ЛОСА
гетерогенная АСБ стеноз до 45-50%, в ВСА гетерогенная АСБ стеноз до 40-45%.
Линейная скорость кровотока (ЛСК) по общим сонным артериям, по внутренним сонным
артериям в пределах возрастной нормы.
3. Диаметр ПА : в пределах нормы с обеих сторон, устья не лоцируются.
ЛСК по позвоночным артериям в интравертебральном отделе в диапазоне нормативных
значений .
Вход позвоночной артерии в канал поперечных отростков шейных позвонков - на уровне С6
позвонка с обеих сторон .
Отмечается непрямолинейность хода позвоночных артерий в интравертебральных сегментах
без локальных изменений ЛСК.
4. Кровоток по подключичным артериям и в брахиоцефальном стволе – магистральный
неизмененный.
5. Внутренняя яремная и подключичная вены проходимы с обеих сторон.
Кровоток по ним фазный, синхронизирован с дыханием
            ''',
            'zakl': '''Ультразвуковые признаки стенозирующего атеросклероза брахиоцефальных
артерий в экстракраниальном отделе, стеноз правой ВСА более 70%''',
            'fio_vrach': 'Иванов П.К.',
            'hospital_did': new_hospital_did
        }
        base_name = "UZI"
        db_manager.add_record(base_name, new_record)

def main():
    populate_test_data()
    with HospitalDBManager() as db_manager:
        # Добавляем новую больницу
        # раскоментите для добавления больницы и узи
        #new_hospital_did = db_manager.add_hospital(
        #hospital_did=3,
        #name="Областной диагностический центр",
        #vc_type=1,
        #endpoint="https://odc.ru/api/Hospital",
        #)

        # Добавляем новую запись УЗИ
        #new_record = {
        #    'vc': 1,
        #    'data_isl': '2024-01-18 11:00:00',
        #    'number_protocol': 2024004,
        #    'FIO': 'Смирнова Ольга Васильевна',
        #    'gender': 'Ж',
        #    'date_birth': '1988-05-12 00:00:00',
        #    'number_med_card': 901234,
        #    'napr_otd': 'Урологическое отделение',
        #    'vid_issled': 'УЗИ почек и мочевого пузыря',
        #    'vc_type': 1,
        #    'scaner': 'Toshiba Aplio 500',
        #    'datchik': 'Конвексный 3.5 МГц',
        #    'opisanie': 'Исследование почек в поперечной и продольной плоскостях. Оценка размеров, структуры, наличия конкрементов.',
        #    'zakl': 'Почки обычных размеров и структуры. Конкрементов не выявлено.',
        #    'fio_vrach': 'Иванов П.К.',
        #    'hospital_did': new_hospital_did
        #}
        #base_name = "UZI"
        #db_manager.add_record(base_name, new_record)


        # Поиск записей по vc
        print("\nПоиск записей по vc:")
        results = db_manager.search_uzi_by_vc(4)
        for result in results:
            print(f"  - {result[3]} (Протокол: {result[2]}, Дата: {result[1]})")
        result=results[0]
        generate_medical_pdf(
            output_file="protocol.pdf",
            date=result[1],
            number_protocol=result[2],
            FIO=result[3],
            gender=result[4],
            date_birth=result[5],
            number_med_cart=result[6],
            nupr_otdel=result[7],
            vid_issled=result[8],
            vc_type=result[9],
            scaner=result[10],
            datchik=result[11],
            opisanie=result[12],
            zakl=result[13],
            fio_vrach=result[14],
            stamp_path = "seal.png"
        )

if __name__ == "__main__":
   # Проверка доступности sqlite3
    print(f"Версия SQLite: {sqlite3.sqlite_version}")

    # Запуск основной функции
    main()
