import builtins

from django import template

register = template.Library()


@register.filter
def abs(value):
    try:
        return builtins.abs(value)
    except (TypeError, ValueError):
        return value
