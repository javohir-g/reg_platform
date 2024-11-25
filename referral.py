# referral.py
from jinja2 import Environment, FileSystemLoader
import pdfkit
from datetime import datetime


def create_referral(client_data):
    """
    Создает PDF направление для клиента на основе шаблона
    """
    env = Environment(loader=FileSystemLoader('templates'))
    template = env.get_template('referral.html')

    # Подготовка данных для шаблона
    context = {
        'client_name': client_data.name,
        'passport_id': client_data.user_passport_id,
        'date_of_birth': client_data.date_of_birth.strftime('%d.%m.%Y'),
        'migrating_country': client_data.migrating_country,
        'current_date': datetime.now().strftime('%d.%m.%Y')
    }

    # Создание HTML
    html_content = template.render(context)

    # Путь для сохранения PDF
    pdf_path = f"referrals/{client_data.user_passport_id}_referral.pdf"

    # Конвертация HTML в PDF
    pdfkit.from_string(html_content, pdf_path)

    return pdf_path

