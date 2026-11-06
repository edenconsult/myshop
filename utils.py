from django.http import HttpResponse
from django.template import loader
import pdfkit
from weasyprint import HTML, CSS
from django.core.exceptions import ImproperlyConfigured

import base64
import json
import logging
from pathlib import Path

from django.conf import settings
from django.contrib.staticfiles import finders

logger = logging.getLogger(__name__)

# Sheets every printed document gets: the compiled Tailwind build plus the
# page rules that only make sense on paper.
PRINT_STYLESHEETS = ("src/output.css", "css/print.css")


def _resolve_static(sheet):
    """Absolute filesystem path for a static-relative file, or None if missing.

    Static-relative names are looked up in the collected tree first (that is
    what a deployment serves), then through the finders so a development
    checkout without collectstatic still resolves them.

    WeasyPrint deliberately reads from disk rather than following a URL: a
    URL would make the view request its own server, which only works
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


def static_image_data_uri(relative_path):
    """A static image inlined as a data: URL, or None if it is missing.

    Printed documents cannot fetch /static/ URLs for the same reason they
    cannot fetch stylesheets, so the receipt embeds its logo this way.
    """
    path = _resolve_static(relative_path)
    if path is None:
        logger.warning("Static image %r not found; prints omit it.", relative_path)
        return None
    mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}.get(
        path.suffix.lower()
    )
    if mime is None:
        logger.warning("Static image %r has an unsupported type.", relative_path)
        return None
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


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


def can_ring_up(user):
    """Both roles work the register: the owner from the hub, the cashier from
    the same screen. Nothing else in the hub is shared between them."""
    return is_admin(user) or is_sale_person(user)


def parse_cart(raw):
    """Read the cart a register posts: one JSON array of line objects.

    Returns the lines, or None when the parameter is not that shape. htmx 2
    stringifies array entries through ``String()`` before sending them, so a
    cart of objects arrives as the literal ``[object Object]``; the registers
    therefore serialise the cart themselves and the view rejects anything it
    cannot read instead of failing part-way through the sale.
    """
    try:
        lines = json.loads(raw) if raw else []
    except json.JSONDecodeError:
        return None
    if not isinstance(lines, list):
        return None
    if not all(isinstance(line, dict) for line in lines):
        return None
    return lines


def image_path(path, instance, filename):
    return f"{path}/{instance.pk}/{filename}"


def render_attached_pdf(relative_template_path, context, file_name, css=None, page_size_mm=None):
    # every printed document can reach the company block without each view
    # remembering to pass it
    html = loader.render_to_string(
        relative_template_path, {**context, "company": settings.COMPANY_INFO}
    )

    stylesheet_paths = []
    for sheet in (*PRINT_STYLESHEETS, *(css or [])):
        path = _resolve_static(sheet)
        if path is None:
            logger.warning(
                "Print stylesheet %r not found; %s will render without it.",
                sheet,
                file_name,
            )
            continue
        stylesheet_paths.append(str(path))

    renderer = getattr(settings, "PDF_RENDERER", "weasyprint").strip().lower()
    if renderer == "wkhtmltopdf":
        options = {"enable-local-file-access": None}
        if page_size_mm:
            options.update(
                {
                    "page-width": f"{page_size_mm[0]}mm",
                    "page-height": f"{page_size_mm[1]}mm",
                }
            )
        configuration = {}
        if settings.WKHTMLTOPDF_PATH:
            configuration["configuration"] = pdfkit.configuration(
                wkhtmltopdf=settings.WKHTMLTOPDF_PATH
            )
        pdf_output = pdfkit.from_string(
            html,
            False,
            css=stylesheet_paths,
            options=options,
            **configuration,
        )
    elif renderer == "weasyprint":
        stylesheets = [CSS(filename=path) for path in stylesheet_paths]
        # WeasyPrint cannot size a page to its content, so a caller that prints
        # on a roll passes the exact sheet it wants; last sheet wins the cascade.
        if page_size_mm:
            stylesheets.append(
                CSS(
                    string=(
                        f"@page {{ size: {page_size_mm[0]}mm "
                        f"{page_size_mm[1]}mm; }}"
                    )
                )
            )
        pdf_output = HTML(string=html).write_pdf(stylesheets=stylesheets)
    else:
        raise ImproperlyConfigured(
            "PDF_RENDERER must be either 'weasyprint' or 'wkhtmltopdf'."
        )

    response = HttpResponse(
        pdf_output,
        content_type="application/pdf",
    )
    response["Content-Disposition"] = (
        f'attachment; filename="{file_name}"'
    )
    return response


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
