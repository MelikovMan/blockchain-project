from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib import colors
from datetime import datetime
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os

# Регистрация шрифта (проверяем наличие файла)
font_path = 'documents/fonts/DejaVuSans.ttf'
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
        date: datetime,
        number_protocol: int,
        FIO: str,
        gender: str,
        date_birth: str,
        number_med_cart: str,
        nupr_otdel: str,
        vid_issled: str,
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
        [Paragraph("Дата и время исследования:", table_text_style), Paragraph(date.strftime("%d.%m.%Y %H:%M"), table_text_style)],
        [Paragraph("Номер протокола:", table_text_style), Paragraph(str(number_protocol), table_text_style)],
        [Paragraph("ФИО больного:", table_text_style), Paragraph(FIO, table_text_style)],
        [Paragraph("Пол:", table_text_style), Paragraph(gender, table_text_style)],
        [Paragraph("Дата рождения:", table_text_style), Paragraph(date_birth, table_text_style)],
        [Paragraph("Номер мед. карты:", table_text_style), Paragraph(number_med_cart, table_text_style)],
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