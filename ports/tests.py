# Copyright (c) 2020-2026 Danilo G. Baio <dbaio@FreeBSD.org>
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
# list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import re
from datetime import timedelta
from pathlib import Path
from unittest import mock

from django.contrib.staticfiles import finders
from django.db import OperationalError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone as dtz

from ports.models import Category, Fallout, Port
from ports.templatetags.link_badge import BADGES, get_link_badge
from ports.templatetags.proxy import get_proxy, get_short_name
from ports.utils import (MAX_REGEX_LENGTH, InvalidRegexError, IsRegex,
                         ValidateRegex)


class IsRegexTests(TestCase):

    def test_plain_text_is_not_a_regex(self):
        self.assertFalse(IsRegex('dbaio'))
        self.assertFalse(IsRegex('dbaio@FreeBSD.org'))
        self.assertFalse(IsRegex(''))

    def test_metacharacters_make_it_a_regex(self):
        self.assertTrue(IsRegex('^www/'))
        self.assertTrue(IsRegex('py.*'))
        self.assertTrue(IsRegex('(a|b)'))

    def test_invalid_pattern_is_not_a_regex(self):
        self.assertFalse(IsRegex('(unclosed'))
        self.assertFalse(IsRegex('*'))

    def test_oversized_pattern_is_not_compiled(self):
        # Reported as a regex so that ValidateRegex can explain the refusal.
        self.assertTrue(IsRegex('a|' * MAX_REGEX_LENGTH))


class ValidateRegexTests(TestCase):

    def test_reasonable_patterns_are_accepted(self):
        for pattern in ['^www/', 'py3[0-9]-.*', '(devel|www)/', 'a+']:
            with self.subTest(pattern=pattern):
                self.assertIsNone(ValidateRegex(pattern))

    def test_nested_quantifiers_are_rejected(self):
        # Catastrophic backtracking: the whole point of the guard.
        for pattern in [r'(a+)+$', r'^(\w+\s?)*$', r'(x{2,})+']:
            with self.subTest(pattern=pattern):
                with self.assertRaises(InvalidRegexError):
                    ValidateRegex(pattern)

    def test_long_patterns_are_rejected(self):
        with self.assertRaises(InvalidRegexError):
            ValidateRegex('a|' * MAX_REGEX_LENGTH)

    def test_python_only_syntax_is_rejected(self):
        # Compiles under Python but the database engine raises OperationalError.
        for pattern in ['(?P<name>abc)', '(?#comment)a', '(?ai)abc']:
            with self.subTest(pattern=pattern):
                with self.assertRaises(InvalidRegexError):
                    ValidateRegex(pattern)


# The site wide cache middleware would otherwise serve a response rendered by a
# previous run, leaving `response.context` empty.
no_cache = override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.dummy.DummyCache'}})


@no_cache
class FilterViewTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        category = Category.objects.create(name='www')
        cls.port = Port.objects.create(origin='www/nginx',
                                       name='nginx',
                                       maintainer='dbaio@FreeBSD.org',
                                       main_category='www')
        cls.port.categories.add(category)

        Fallout.objects.create(port=cls.port,
                               env='head-amd64-default',
                               version='1.0',
                               category='build',
                               maintainer='dbaio@FreeBSD.org',
                               last_committer='dbaio@FreeBSD.org',
                               date=dtz.now() - timedelta(days=1),
                               log_url='https://pkg-status.freebsd.org/beefy18/x.log',
                               build_url='https://pkg-status.freebsd.org/beefy18/',
                               report_url='https://lists.freebsd.org/1.html')

    def test_fallout_list_accepts_a_safe_regex(self):
        response = self.client.get(reverse('ports:fallout'), {'port': '^www/'})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context['filter_error'])
        self.assertEqual(len(response.context['fallout_list']), 1)

    def test_fallout_list_rejects_a_catastrophic_regex(self):
        response = self.client.get(reverse('ports:fallout'), {'maintainer': '(a+)+$'})
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.context['filter_error'])
        self.assertEqual(len(response.context['fallout_list']), 0)

    def test_port_list_rejects_a_catastrophic_regex(self):
        response = self.client.get(reverse('ports:list'), {'port': r'^(\w+\s?)*$'})
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.context['filter_error'])

    def test_database_error_becomes_a_message(self):
        """A regex the guard let through must not reach the user as a 500"""

        calls = []

        def flaky_count(*args, **kwargs):
            calls.append(1)
            if len(calls) == 1:
                raise OperationalError('Illegal argument to a regular expression')
            return 0

        with mock.patch('django.core.paginator.Paginator.count',
                        new_callable=mock.PropertyMock, side_effect=flaky_count):
            response = self.client.get(reverse('ports:fallout'), {'env': 'head.*'})

        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.context['filter_error'])

    def test_pages_render_without_filters(self):
        for name in ['ports:index', 'ports:fallout', 'ports:list',
                     'ports:server', 'ports:about', 'ports:build_env',
                     'ports:maintainer']:
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)


@no_cache
class PaginationTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(name='www')
        cls.port = Port.objects.create(origin='www/nginx', name='nginx',
                                       maintainer='dbaio@FreeBSD.org', main_category='www')
        cls.port.categories.add(cls.category)
        Fallout.objects.create(
            port=cls.port, env='head-amd64-default', version='1.0', category='build',
            maintainer='dbaio@FreeBSD.org', last_committer='x@FreeBSD.org', date=dtz.now(),
            log_url='https://pkg-status.freebsd.org/beefy18/x.log',
            build_url='https://pkg-status.freebsd.org/beefy18/',
            report_url='https://lists.freebsd.org/1.html')

    def test_page_past_the_end_serves_the_last_page(self):
        """Narrowing a filter leaves a stale `page`; that must not be a 404"""
        response = self.client.get(reverse('ports:fallout'),
                                   {'page': '2', 'categories': 'www'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['page_obj'].number, 1)

    def test_nonsense_page_serves_the_first_page(self):
        for page in ['abc', '0', '-1', '']:
            with self.subTest(page=page):
                response = self.client.get(reverse('ports:fallout'), {'page': page})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context['page_obj'].number, 1)

    def test_pagination_links_keep_every_repeated_value(self):
        """request.GET.items would drop all but the last `categories`"""
        for name in ['devel', 'x11']:
            self.port.categories.add(Category.objects.create(name=name))
        for index in range(60):
            Fallout.objects.create(
                port=self.port, env='head-amd64-default', version='1.0', category='build',
                maintainer='dbaio@FreeBSD.org', last_committer='x@FreeBSD.org',
                date=dtz.now() - timedelta(hours=index),
                log_url=f'https://pkg-status.freebsd.org/beefy18/{index}.log',
                build_url='https://pkg-status.freebsd.org/beefy18/',
                report_url='https://lists.freebsd.org/1.html')

        response = self.client.get(
            reverse('ports:fallout') + '?categories=www&categories=devel&categories=x11')
        links = re.findall(r'href="(\?page=2[^"]*)"', response.content.decode())
        self.assertTrue(links, 'expected a link to page 2')
        self.assertEqual(links[0].count('categories='), 3)


@no_cache
class ThemeToggleTests(TestCase):

    def test_the_toggle_and_its_script_are_present(self):
        html = self.client.get(reverse('ports:index')).content.decode()
        self.assertIn('id="theme-toggle"', html)
        self.assertIn('theme_toggle.js', html)
        # The stored theme is stamped before the first paint.
        self.assertIn('themePreference', html)

    def test_the_markup_carries_no_theme(self):
        """The theme is applied client side, so the HTML stays cacheable

        Rendering it server side would let the site wide cache serve one
        visitor's theme to the next.
        """
        response = self.client.get(reverse('ports:index'), HTTP_COOKIE='themePreference=dark')
        self.assertNotIn('<html lang="en" data-theme', response.content.decode())


@no_cache
class EmptyDatabaseTests(TestCase):

    def test_dashboard_survives_an_empty_database(self):
        # Used to raise IndexError on the most recent/oldest lookups.
        response = self.client.get(reverse('ports:index'))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context['fallout_recent'])


@no_cache
class ApiTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.port = Port.objects.create(origin='www/nginx',
                                       name='nginx',
                                       maintainer='dbaio@FreeBSD.org',
                                       main_category='www')

    def test_limit_is_capped(self):
        response = self.client.get('/api/port/', {'limit': '1000000'})
        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(response.json()['results']), 500)


class StaticFilesTests(TestCase):

    STATIC_TAG_RE = re.compile(r'{%\s*static\s+["\']([^"\']+)["\']')

    def test_every_static_path_resolves(self):
        """A path the finders cannot resolve breaks the page under the toolbar

        `{% static %}` happily returns a URL for a path that does not exist, or
        for one written with a leading slash, but anything that calls
        `finders.find()` on it -- the debug toolbar does, while rendering --
        raises instead.
        """

        templates = Path(__file__).parent.joinpath('templates').rglob('*.html')
        checked = 0

        for template in templates:
            for path in self.STATIC_TAG_RE.findall(template.read_text()):
                with self.subTest(template=template.name, path=path):
                    self.assertFalse(path.startswith('/'),
                                     'static paths are relative to the static root')
                    self.assertIsNotNone(finders.find(path), 'static file not found')
                    checked += 1

        self.assertGreater(checked, 0, 'no static tags found, the regex is wrong')


class TemplateTagTests(TestCase):

    def test_get_proxy_rewrites_nyi_urls(self):
        self.assertEqual(get_proxy('http://beefy18.nyi.freebsd.org/data/x.log'),
                         'https://pkg-status.freebsd.org/beefy18/data/x.log')

    def test_get_proxy_passes_other_urls_through(self):
        # Used to raise AttributeError on a non-matching URL.
        url = 'https://pkg-status.freebsd.org/beefy18/data/x.log'
        self.assertEqual(get_proxy(url), url)
        self.assertEqual(get_proxy(''), '')

    def test_get_short_name(self):
        self.assertEqual(get_short_name('Beefy18.nyi.FreeBSD.org'), 'beefy18')

    def test_get_link_badge_cycles(self):
        self.assertEqual(get_link_badge(1), BADGES[0])
        self.assertEqual(get_link_badge(len(BADGES)), BADGES[-1])
        self.assertEqual(get_link_badge(len(BADGES) + 1), BADGES[0])
