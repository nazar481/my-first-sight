from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Получить значение из словаря по ключу"""
    return dictionary.get(key)

@register.filter
def sum_attr(queryset, attr):
    """Сумма значений атрибута в queryset"""
    return sum(getattr(obj, attr) for obj in queryset)

@register.filter
def divisibleby(value, arg):
    """Деление с проверкой на ноль"""
    try:
        return (int(value) / int(arg)) * 100
    except (ValueError, ZeroDivisionError):
        return 0