from django import template
import re

register = template.Library()

@register.filter(is_safe=True)
def get_proxy(url_log):
    match = re.search('http://(.*).nyi.freebsd.org/(.*)', url_log, re.IGNORECASE)
    return f'https://pkg-status.freebsd.org/{match.group(1)}/{match.group(2)}'

@register.filter(is_safe=True)
def get_short_name(server):
    return server.lower().split('.')[0]
