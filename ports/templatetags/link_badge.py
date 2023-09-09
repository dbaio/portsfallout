from django import template
import re

register = template.Library()

@register.filter(is_safe=True)
def get_link_badge(loop_count):
    badges = ['badge-secondary',
              'badge-info',
              'badge-light',
              'badge-dark',
              'badge-warning',
              'badge-primary',
              'badge-success',
              'badge-danger',
              ]
    while loop_count > len(badges):
        loop_count = loop_count - len(badges)

    return badges[loop_count - 1]



