"""Icon tags: every glyph ships in a local sprite instead of an icon web font."""

from django import template
from django.templatetags.static import static
from django.utils.html import format_html

register = template.Library()

SPRITE = "icons/sprite.svg"


@register.simple_tag
def icon(name, classes=""):
    """One sprite symbol; the caller's text-[Npx] class sizes it (see .ms-icon)."""
    return format_html(
        '<svg class="ms-icon {}" aria-hidden="true" focusable="false">'
        '<use href="{}#{}"></use></svg>',
        classes,
        static(SPRITE),
        name,
    )
