from django.http import HttpResponse
from django.template import loader
import pdfkit
from django.template import loader
from weasyprint import HTML, CSS

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
    for css_file in (css or []):
        stylesheets.append(CSS(filename=str(css_file)))

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
