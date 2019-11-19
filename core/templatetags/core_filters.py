from django import template

register = template.Library()


@register.filter
def page_range(value):
    return range(1, value + 1)
