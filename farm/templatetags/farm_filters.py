import builtins

from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def abs(value):
    try:
        return builtins.abs(value)
    except (TypeError, ValueError):
        return value


@register.filter
def gender_icon(gender):
    """Return a colored gender icon span for the given gender value."""
    if not gender:
        return ''
    female = gender in ('Doe', 'Doeling')
    css = 'female' if female else 'male'
    symbol = '\u2640' if female else '\u2642'
    return mark_safe(f'<span class="gender-icon {css}">{symbol}</span>')
