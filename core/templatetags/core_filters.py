from django import template

register = template.Library()


@register.filter
def page_range(value):
    return range(1, value + 1)


@register.filter
def mult(value, arg):
    return (value*arg)


@register.filter(is_safe=True)
def split_by(value, arg):
    return value.split(arg)


@register.filter
def get_nth_item(value, arg):
    return value[arg]


@register.filter
def replace_slash_with_dash(value):
    return "-".join(value.split('/')[1:-1])


@register.filter
def divide_by_col(value):
    return int(12/(len(value)))
