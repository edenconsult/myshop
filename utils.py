from django.http import HttpResponse
from django.template import loader
import pdfkit
from django.template import loader
from weasyprint import HTML, CSS

import logging
from pathlib import Path

from django.conf import settings
from django.contrib.staticfiles import finders

logger = logging.getLogger(__name__)

# Sheets every printed document gets: the compiled Tailwind build plus the
# page rules that only make sense on paper.
PRINT_STYLESHEETS = ("src/output.css", "css/print.css")


def _resolve_stylesheet(sheet):
    """Absolute filesystem path for a stylesheet, or None if it is missing.

    Static-relative names are looked up in the collected tree first (that is
    what a deployment serves), then through the finders so a development
    checkout without collectstatic still resolves them.

    WeasyPrint deliberately reads from disk rather than following a stylesheet
    URL: a URL would make the view request its own server, which only works
    while a dev server happens to be listening on that port and blocks a
    single-worker deployment.
    """
    path = Path(sheet)
    if path.is_absolute() or path.is_file():
        return path if path.is_file() else None

    collected = Path(settings.STATIC_ROOT) / sheet
    if collected.is_file():
        return collected

    found = finders.find(sheet)
    return Path(found) if found else None


def get_uuid(id):
    import uuid

    try:
        uid = uuid.UUID(id)
    except ValueError:
        return None
    else:
        return uid


def is_admin(user):
    return user.user_type == "ADMIN"


def is_sale_person(user):
    return user.user_type == "SALEPERSON"


def image_path(path, instance, filename):
    return f"{path}/{instance.pk}/{filename}"


def render_attached_pdf(relative_template_path, context, file_name, css=None):
    html = loader.render_to_string(relative_template_path, context)

    stylesheets = []
    for sheet in (*PRINT_STYLESHEETS, *(css or [])):
        path = _resolve_stylesheet(sheet)
        if path is None:
            logger.warning(
                "Print stylesheet %r not found; %s will render without it.",
                sheet,
                file_name,
            )
            continue
        stylesheets.append(CSS(filename=str(path)))

    pdf_output = HTML(
        string=html,
    ).write_pdf(stylesheets=stylesheets)

    response = HttpResponse(
        pdf_output,
        content_type="application/pdf",
    )
    response["Content-Disposition"] = (
        f'attachment; filename="{file_name}"'
    )
    return response

#
# def render_attached_pdf(relative_template_path, context, file_name, css=[]):
#     html = loader.render_to_string(relative_template_path, context)
#
#     config = pdfkit.configuration(
#         wkhtmltopdf=r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
#     )
#     output = pdfkit.from_string(
#         html, output_path=False, css=css if len(css) > 0 else [],
#         configuration=config,
#     )
#     response = HttpResponse(output)
#     response["Content-Type"] = "application/pdf"
#     response["Content-Disposition"] = "attachment; filename=%s" % (file_name)
#     return response


def generate_code(max_length=4):
    """Args:
        max_length (int, optional): _description_. Defaults to 4.

    Returns:
        _type_: str
    """
    import string
    from random import choices

    letters = string.ascii_uppercase + string.digits
    return "".join(choices(letters, k=max_length))
