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
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
from unittest import mock

import requests
from django.contrib.staticfiles import finders
from django.core.management import call_command
from django.db import IntegrityError, OperationalError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone as dtz

from ports.management.commands.find_orphan_fallouts import (
    LOG_HEAD_BYTES, LOG_TAIL_BYTES, Command as FindOrphanFallouts)
from ports.models import Category, Fallout, Port
from ports.templatetags.build_env import env_split, osversion
from ports.templatetags.commit import COMMIT_MIRRORS, commit_mirrors
from ports.templatetags.phase import PHASE_FAMILIES, phase_family
from ports.templatetags.proxy import get_proxy, get_short_name
from ports.utils import (LOG_HEADER_FIELDS, MAX_REGEX_LENGTH,
                         InvalidRegexError, IsRegex, ParseLogHeader,
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
class MobileLabelTests(TestCase):
    """Below 700px the list tables stack, and each cell shows `data-label`

    A column added without one renders as a value with no name on a phone,
    which is invisible from a desktop browser.
    """

    @classmethod
    def setUpTestData(cls):
        category = Category.objects.create(name='www')
        cls.port = Port.objects.create(origin='www/nginx', name='nginx',
                                       maintainer='dbaio@FreeBSD.org', main_category='www')
        cls.port.categories.add(category)
        Fallout.objects.create(
            port=cls.port, env='head-amd64-default', version='1.0', category='build',
            maintainer='dbaio@FreeBSD.org', last_committer='x@FreeBSD.org', date=dtz.now(),
            log_url='https://pkg-status.freebsd.org/beefy18/x.log',
            build_url='https://pkg-status.freebsd.org/beefy18/',
            report_url='https://lists.freebsd.org/1.html')

    def unlabelled_cells(self, html):
        """Cells past the first in a row, inside a .table-wrap, with no label"""

        wraps = re.findall(r'<div class="table-wrap">(.*?)</table>', html, re.S)
        missing = []
        for wrap in wraps:
            for row in re.findall(r'<tr>(.*?)</tr>', wrap, re.S):
                for cell in re.findall(r'<td([^>]*)>', row)[1:]:
                    if 'data-label' not in cell:
                        missing.append(cell.strip())
        return missing

    def test_list_pages_label_every_cell(self):
        for url in [reverse('ports:fallout'), reverse('ports:list'),
                    reverse('ports:server'), reverse('ports:build_env'),
                    reverse('ports:maintainer'),
                    reverse('ports:detail', args=[self.port.origin])]:
            with self.subTest(url=url):
                html = self.client.get(url).content.decode()
                self.assertEqual(self.unlabelled_cells(html), [])

    def test_the_dashboard_cards_are_left_alone(self):
        """They are two columns and already read fine on a phone"""
        html = self.client.get(reverse('ports:index')).content.decode()
        self.assertNotIn('table-wrap', html)
        self.assertNotIn('data-label', html)


@no_cache
class PortDetailUrlTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.port = Port.objects.create(
            origin='www/apache24', name='apache24', main_category='www',
            maintainer='dbaio@FreeBSD.org')

    def test_the_url_carries_the_origin(self):
        self.assertEqual(self.port.get_absolute_url(), '/port/www/apache24/')

    def test_the_origin_serves_the_port(self):
        response = self.client.get(self.port.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['port'], self.port)

    def test_an_unknown_origin_is_a_404(self):
        self.assertEqual(self.client.get('/port/www/nope/').status_code, 404)

    def test_the_id_still_reaches_the_port(self):
        response = self.client.get(reverse('ports:detail_by_id', args=[self.port.id]))
        self.assertRedirects(response, self.port.get_absolute_url(), status_code=301)

    def test_an_unknown_id_is_a_404(self):
        url = reverse('ports:detail_by_id', args=[self.port.id + 1])
        self.assertEqual(self.client.get(url).status_code, 404)


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


@no_cache
class ApiFilterTests(TestCase):
    """The per field filters of the API

    `ports` as a maintainer is the case the fixtures are built around: it is a
    prefix of one address, the middle of another, and part of a third origin.
    """

    @classmethod
    def setUpTestData(cls):
        cls.now = dtz.now()
        cls.ports = cls.fallout('devel/opencl-clang', 'ports@FreeBSD.org',
                                env='144amd64-quarterly', flavor='llvm16', days=1)
        cls.dbaio = cls.fallout('www/nginx', 'dbaio@FreeBSD.org',
                                env='head-amd64-default', days=5)
        # The origin, not the maintainer, is what holds `ports` here.
        cls.pkg = cls.fallout('ports-mgmt/pkg', 'bapt@FreeBSD.org',
                              env='head-amd64-default', days=9)
        # And here the address merely contains it.
        cls.convectix = cls.fallout('x11/foo', 'fbsd-ports@convectix.com',
                                    env='head-i386-default', days=13)

    @classmethod
    def fallout(cls, origin, maintainer, env, flavor='', days=0):
        port = Port.objects.create(origin=origin, name=origin.split('/')[1],
                                   maintainer=maintainer,
                                   main_category=origin.split('/')[0])
        return Fallout.objects.create(
            port=port, env=env, version='1.0', category='build', flavor=flavor,
            maintainer=maintainer, last_committer='x@FreeBSD.org',
            date=cls.now - timedelta(days=days),
            log_url=f'https://pkg-status.freebsd.org/beefy18/{port.name}.log',
            build_url='https://pkg-status.freebsd.org/beefy18/',
            report_url='https://lists.freebsd.org/1.html')

    def maintainers(self, params, endpoint='/api/fallout/'):
        response = self.client.get(endpoint, params)
        self.assertEqual(response.status_code, 200)
        return sorted(row['maintainer'] for row in response.json()['results'])

    def test_maintainer_matches_from_the_start_of_the_address(self):
        self.assertEqual(self.maintainers({'maintainer': 'ports'}),
                         ['ports@FreeBSD.org'])

    def test_search_is_the_reason_that_filter_exists(self):
        """`search` matches a substring of any searched field, `maintainer` does not"""

        self.assertEqual(self.maintainers({'search': 'ports'}),
                         ['bapt@FreeBSD.org', 'fbsd-ports@convectix.com',
                          'ports@FreeBSD.org'])

    def test_the_full_address_still_works(self):
        self.assertEqual(self.maintainers({'maintainer': 'ports@FreeBSD.org'}),
                         ['ports@FreeBSD.org'])

    def test_maintainer_takes_a_regular_expression(self):
        self.assertEqual(self.maintainers({'maintainer': '^(ports|dbaio)@'}),
                         ['dbaio@FreeBSD.org', 'ports@FreeBSD.org'])

    def test_filters_are_combined(self):
        self.assertEqual(self.maintainers({'env': 'head-amd64', 'port': 'ports-mgmt'}),
                         ['bapt@FreeBSD.org'])
        self.assertEqual(self.maintainers({'maintainer': 'ports', 'env': 'head-amd64'}), [])

    def test_flavor_and_the_build_phase(self):
        self.assertEqual(self.maintainers({'flavor': 'llvm16'}), ['ports@FreeBSD.org'])
        self.assertEqual(len(self.maintainers({'category': 'build'})), 4)
        self.assertEqual(self.maintainers({'category': 'buil'}), [])

    def test_an_empty_filter_is_ignored(self):
        self.assertEqual(len(self.maintainers({'maintainer': '', 'env': ' '})), 4)

    def test_the_port_endpoint_filters_the_same_way(self):
        self.assertEqual(self.maintainers({'maintainer': 'ports'}, '/api/port/'),
                         ['ports@FreeBSD.org'])
        self.assertEqual(self.maintainers({'port': 'ports-mgmt'}, '/api/port/'),
                         ['bapt@FreeBSD.org'])

    def test_the_category_endpoint_filters_by_name(self):
        Category.objects.create(name='devel')
        Category.objects.create(name='www')
        response = self.client.get('/api/category/', {'name': '^de'})
        self.assertEqual([row['name'] for row in response.json()['results']], ['devel'])

    def test_a_refused_regex_is_a_400(self):
        response = self.client.get('/api/fallout/', {'maintainer': 'bogus((a+)+)b'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('nested quantifiers', response.json()['maintainer'][0])

    def test_a_filter_the_database_refuses_is_a_400(self):
        """The engine has the last word, and it only speaks once the query runs"""

        with mock.patch('django.db.models.query.QuerySet.count',
                        side_effect=OperationalError('Illegal argument to a regular expression')):
            response = self.client.get('/api/fallout/', {'env': 'head.*'})

        self.assertEqual(response.status_code, 400)
        self.assertIn('could not be evaluated', response.json()['detail'][0])

    def test_a_date_range_bounds_both_ends(self):
        recent = (self.now - timedelta(days=3)).date().isoformat()
        self.assertEqual(self.maintainers({'date_after': recent}), ['ports@FreeBSD.org'])
        self.assertEqual(len(self.maintainers({'date_before': recent})), 3)

    def test_a_date_range_takes_a_timestamp_too(self):
        moment = (self.now - timedelta(days=3)).isoformat()
        self.assertEqual(self.maintainers({'date_after': moment}), ['ports@FreeBSD.org'])

    def test_a_value_that_is_not_a_date_is_a_400(self):
        for value in ['yesterday', '2026-02-31', '2026-13-01']:
            with self.subTest(value=value):
                response = self.client.get('/api/fallout/', {'date_after': value})
                self.assertEqual(response.status_code, 400)
                self.assertIn('Expected a date', response.json()['date_after'][0])

    def test_the_browsable_api_offers_the_filters(self):
        response = self.client.get('/api/fallout/', {'search': 'nginx'}, HTTP_ACCEPT='text/html')
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        for param in ['maintainer', 'env', 'flavor', 'date_after']:
            with self.subTest(param=param):
                self.assertIn(f'name="{param}"', body)

        # Filtering from that form must not throw away the search in the URL.
        self.assertIn('name="search" value="nginx"', body)


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

    def test_env_split_separates_the_branch(self):
        self.assertEqual(env_split('144arm64-quarterly'),
                         {'head': '144arm64', 'branch': '-quarterly',
                          'quarterly': True})
        self.assertEqual(env_split('main-amd64-default'),
                         {'head': 'main-amd64', 'branch': '-default',
                          'quarterly': False})

    def test_env_split_keeps_unknown_names_whole(self):
        # The two halves have to concatenate back into the original, so a name
        # that ends in something else must not lose its tail.
        for name in ('143i386-experimental', 'somethingelse', ''):
            parts = env_split(name)
            self.assertEqual(parts['head'], name)
            self.assertEqual(parts['branch'], '')
            self.assertFalse(parts['quarterly'])

    def test_phase_family_groups_known_phases(self):
        self.assertEqual(phase_family('build'), 'build')
        self.assertEqual(phase_family('configure'), 'build')
        self.assertEqual(phase_family('lib-depends'), 'dep')
        self.assertEqual(phase_family('checksum'), 'src')
        self.assertEqual(phase_family('package'), 'pkg')

    def test_phase_family_ignores_the_reason_suffix(self):
        # Real data carries these: the tail says how the build died, not where.
        self.assertEqual(phase_family('build/runaway'), 'build')
        self.assertEqual(phase_family('configure/runaway'), 'build')
        self.assertEqual(phase_family('package/timeout'), 'pkg')
        self.assertEqual(phase_family('extract/timeout'), 'src')

    def test_phase_family_falls_back_for_anything_else(self):
        # The phase is whatever the log reported, so it still has to render.
        self.assertEqual(phase_family('some-new-poudriere-phase'), 'none')
        self.assertEqual(phase_family(''), 'none')
        self.assertEqual(phase_family(None), 'none')

    def test_osversion_reads_the_release_out_of_the_number(self):
        self.assertEqual(osversion('1404000'), '14.4')
        self.assertEqual(osversion('1500068'), '15.0')
        self.assertEqual(osversion('1600019'), '16.0')
        # Six digits, from the releases before 10.
        self.assertEqual(osversion('903000'), '9.3')

    def test_osversion_passes_anything_else_through(self):
        for value in ('', None, 'unknown'):
            self.assertEqual(osversion(value), str(value or '').strip())

    def test_commit_mirrors_carry_the_hash(self):
        commit = 'a2cdb8be472c8c66cf9304ac4e984682d7d24ffc'
        mirrors = commit_mirrors(commit)

        self.assertEqual(len(mirrors), len(COMMIT_MIRRORS))
        for mirror in mirrors:
            with self.subTest(mirror=mirror['name']):
                self.assertTrue(mirror['url'].endswith(commit))
                self.assertTrue(mirror['url'].startswith('https://'))

    def test_commit_mirrors_accept_the_short_hashes(self):
        # The logs from before 2026 carry nine to eleven characters.
        self.assertEqual(len(commit_mirrors('2e0e0c62c')), len(COMMIT_MIRRORS))

    def test_commit_mirrors_refuse_anything_that_is_not_a_hash(self):
        """A value read from a log has no business being pasted into a URL"""

        for value in ('', None, 'no', 'HEAD', '../../etc', 'z' * 40,
                      'a' * 41, 'abc'):
            with self.subTest(value=value):
                self.assertEqual(commit_mirrors(value), [])


# The header poudriere writes at the top of a build log, quoted verbatim by the
# fallout mail. Kept whole so the parser is tested against the real shape of it.
LOG_HEADER = """\
=>> Building textproc/py-hieroglyph
build started at Tue Aug  4 21:03:38 UTC 2026
port directory: /usr/ports/textproc/py-hieroglyph
package name: py312-hieroglyph-2.1.0_1
building for: FreeBSD 144i386-quarterly-job-11 14.4-RELEASE-p8 FreeBSD 14.4-RELEASE-p8 i386
maintained by: dbaio@FreeBSD.org
Makefile datestamp: -rw-r--r--  1 root wheel 592 Jul  9 01:01 /usr/ports/textproc/py-hieroglyph/Makefile
Ports top last git commit: a2cdb8be472c8c66cf9304ac4e984682d7d24ffc
Ports top unclean checkout: no
Port dir last git commit: e9e40e40c5d926e4d17c156665b69e8073cc863b
Port dir unclean checkout: no
Poudriere version: poudriere-git-3.4.8
Host OSVERSION: 1600019
Jail OSVERSION: 1404000
Job Id: 11

---Begin Environment---
SHELL=/bin/sh
OSVERSION=1404000
---End Environment---
"""

LOG_HEADER_VALUES = {
    'package_name': 'py312-hieroglyph-2.1.0_1',
    'ports_top_commit': 'a2cdb8be472c8c66cf9304ac4e984682d7d24ffc',
    'port_dir_commit': 'e9e40e40c5d926e4d17c156665b69e8073cc863b',
    'poudriere_version': 'poudriere-git-3.4.8',
    'host_osversion': '1600019',
    'jail_osversion': '1404000',
}


class LogHeaderTests(TestCase):

    def test_every_field_is_read(self):
        self.assertEqual(ParseLogHeader(LOG_HEADER), LOG_HEADER_VALUES)

    def test_the_rest_of_the_log_follows_the_header(self):
        log = LOG_HEADER + '\n'.join([
            '=======================<phase: build         >=====================',
            'package name: not-the-header-1.0',
            '*** Error code 1',
        ])
        self.assertEqual(ParseLogHeader(log)['package_name'],
                         'py312-hieroglyph-2.1.0_1')

    def test_a_log_without_the_block_yields_empty_fields(self):
        """The result goes straight to the model, so it is never short a key"""

        for log in ('', None, 'Log URL: https://pkg-status.freebsd.org/x.log'):
            with self.subTest(log=log):
                details = ParseLogHeader(log)
                self.assertEqual(sorted(details),
                                 sorted(LOG_HEADER_VALUES))
                self.assertEqual(set(details.values()), {''})

    def test_a_partial_block_keeps_what_it_has(self):
        log = ('=>> Building www/nginx\n'
               'package name: nginx-1.28.0\n'
               '\n---Begin Environment---\n')
        details = ParseLogHeader(log)
        self.assertEqual(details['package_name'], 'nginx-1.28.0')
        self.assertEqual(details['poudriere_version'], '')

    def test_a_block_without_an_environment_dump_is_still_read(self):
        # A log cut short mid-build has no `---Begin Environment---` to stop at.
        log = LOG_HEADER.split('---Begin Environment---')[0]
        self.assertEqual(ParseLogHeader(log), LOG_HEADER_VALUES)

    def test_an_oversized_value_is_trimmed_to_the_field(self):
        log = f'=>> Building www/nginx\npackage name: {"x" * 400}\n'
        _, max_length = LOG_HEADER_FIELDS['package name']
        self.assertEqual(len(ParseLogHeader(log)['package_name']), max_length)

    def test_the_lengths_match_the_model(self):
        """Trimming to a length the column does not have would still fail"""

        for field, max_length in LOG_HEADER_FIELDS.values():
            with self.subTest(field=field):
                self.assertEqual(Fallout._meta.get_field(field).max_length,
                                 max_length)


@no_cache
class FalloutDetailTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.port = Port.objects.create(origin='textproc/py-hieroglyph',
                                       name='py-hieroglyph',
                                       maintainer='dbaio@FreeBSD.org',
                                       main_category='textproc')
        cls.fallout = Fallout.objects.create(
            port=cls.port, env='144i386-quarterly', version='2.1.0_1',
            category='build', maintainer='dbaio@FreeBSD.org',
            last_committer='dbaio@FreeBSD.org', date=dtz.now(),
            log_url='https://pkg-status.freebsd.org/beefy18/x.log',
            build_url='https://pkg-status.freebsd.org/beefy18/',
            report_url='https://lists.freebsd.org/1.html',
            server='beefy18.nyi.freebsd.org', **LOG_HEADER_VALUES)

    def test_the_log_details_are_on_the_page(self):
        html = self.client.get(
            reverse('ports:fdetail', args=[self.fallout.id])).content.decode()

        for value in LOG_HEADER_VALUES.values():
            with self.subTest(value=value):
                self.assertIn(value, html)

        # The OSVERSIONs stay whole -- that is the number a porter looks up --
        # with the release they belong to next to them.
        self.assertIn('FreeBSD 14.4', html)
        self.assertIn('FreeBSD 16.0', html)

    def test_the_osversions_link_to_the_handbook(self):
        html = self.client.get(
            reverse('ports:fdetail', args=[self.fallout.id])).content.decode()
        self.assertEqual(
            html.count('docs.freebsd.org/en/books/porters-handbook/versions/'), 2)

    def test_both_commits_link_to_every_mirror(self):
        html = self.client.get(
            reverse('ports:fdetail', args=[self.fallout.id])).content.decode()

        for commit in (LOG_HEADER_VALUES['ports_top_commit'],
                       LOG_HEADER_VALUES['port_dir_commit']):
            for name, url in COMMIT_MIRRORS:
                with self.subTest(commit=commit, mirror=name):
                    self.assertIn(url.format(commit).replace('&', '&amp;'), html)

    def test_a_fallout_imported_before_the_details_still_renders(self):
        """Most of the archive predates them, and every field is optional"""

        bare = Fallout.objects.create(
            port=self.port, env='144i386-quarterly', version='2.0', category='build',
            maintainer='dbaio@FreeBSD.org', last_committer='', date=dtz.now(),
            log_url='https://pkg-status.freebsd.org/beefy18/y.log',
            build_url='https://pkg-status.freebsd.org/beefy18/',
            report_url='https://lists.freebsd.org/2.html')

        response = self.client.get(reverse('ports:fdetail', args=[bare.id]))
        self.assertEqual(response.status_code, 200)
        # Nothing known about the tree, so the section is left out entirely.
        self.assertNotIn('Ports tree', response.content.decode())


class FillLogDetailsTests(TestCase):
    """The backfill command, whose only input is the report page it fetched"""

    # What the archive serves: the mail in a `pre`, with its markup escaped.
    REPORT = ('<html><body><article><pre class="main">'
              + LOG_HEADER.replace('>', '&gt;') +
              '</pre></article></body></html>')

    @classmethod
    def setUpTestData(cls):
        cls.port = Port.objects.create(origin='textproc/py-hieroglyph',
                                       name='py-hieroglyph',
                                       maintainer='dbaio@FreeBSD.org',
                                       main_category='textproc')

    def make_fallout(self, **overrides):
        fields = dict(
            port=self.port, env='144i386-quarterly', version='2.1.0_1',
            category='build', maintainer='dbaio@FreeBSD.org',
            last_committer='', date=dtz.now(),
            log_url='https://pkg-status.freebsd.org/beefy18/x.log',
            build_url='https://pkg-status.freebsd.org/beefy18/',
            report_url='https://lists.freebsd.org/1.html')
        fields.update(overrides)
        return Fallout.objects.create(**fields)

    def run_command(self, page=REPORT, fail=False):
        response = mock.Mock(text=page)
        response.raise_for_status.return_value = None
        get = mock.Mock(return_value=response)
        if fail:
            get.side_effect = requests.RequestException('boom')

        with mock.patch('ports.management.commands.fill_log_details.requests.get', get):
            call_command('fill_log_details', '--delay', '0', verbosity=0)

        return get

    def test_a_fallout_without_details_is_filled_from_its_report(self):
        fallout = self.make_fallout()
        self.run_command()

        fallout.refresh_from_db()
        for field, value in LOG_HEADER_VALUES.items():
            with self.subTest(field=field):
                self.assertEqual(getattr(fallout, field), value)

    def test_a_fallout_that_has_them_is_not_fetched_again(self):
        self.make_fallout(**LOG_HEADER_VALUES)
        self.assertEqual(self.run_command().call_count, 0)

    def test_a_fallout_with_no_report_is_left_alone(self):
        self.make_fallout(report_url='')
        self.assertEqual(self.run_command().call_count, 0)

    def test_a_report_that_cannot_be_read_leaves_the_row_alone(self):
        """It is picked up by the next run rather than marked as done"""

        fallout = self.make_fallout()
        self.run_command(fail=True)

        fallout.refresh_from_db()
        self.assertEqual(fallout.package_name, '')

    def test_a_report_without_a_log_header_leaves_the_row_alone(self):
        fallout = self.make_fallout()
        self.run_command(page='<html><body><pre class="main">no log here</pre></body></html>')

        fallout.refresh_from_db()
        self.assertEqual(fallout.package_name, '')

    def test_the_older_mailman_pages_are_read_too(self):
        # Kept from before May 2021, and their `pre` carries no class.
        fallout = self.make_fallout()
        self.run_command(page='<html><body><pre>'
                              + LOG_HEADER.replace('>', '&gt;') + '</pre></body></html>')

        fallout.refresh_from_db()
        self.assertEqual(fallout.package_name, LOG_HEADER_VALUES['package_name'])


class OrphanLogReadTests(TestCase):
    """Reading a build log without pulling the whole of it into memory"""

    LOG_URL = ('https://pkg-status.freebsd.org/beefy19/data/144i386-quarterly/'
               '17af07f5de95/logs/py312-hieroglyph-2.1.0_1.log')

    ENDING = ('build of textproc/py-hieroglyph | py312-hieroglyph-2.1.0_1 '
              'ended at Tue Aug  4 21:05:11 UTC 2026')

    # Bigger than the head, so the two ends of the result cannot overlap.
    HUGE = 4 * 1024 * 1024

    def make_log(self, filler=0):
        return (LOG_HEADER
                + 'MASTERNAME=144i386-quarterly\n'
                + '=======================<phase: build-depends  >====================\n'
                + '=======================<phase: lib-depends    >====================\n'
                + 'x' * filler + '\n'
                + '*** Error code 1\n'
                + self.ENDING + '\n')

    def command(self):
        return FindOrphanFallouts(stdout=StringIO())

    def fetch(self, body):
        """Read a log served a chunk at a time, as a streamed response is"""

        raw = body.encode()
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.raise_for_status.return_value = None
        response.iter_content.side_effect = lambda chunk_size: (
            raw[at:at + chunk_size] for at in range(0, len(raw), chunk_size))

        with mock.patch('ports.management.commands.find_orphan_fallouts.requests.get',
                        mock.Mock(return_value=response)):
            return self.command().fetch_log_content(self.LOG_URL)

    def test_a_huge_log_costs_only_its_two_ends(self):
        head, tail = self.fetch(self.make_log(filler=self.HUGE))

        self.assertEqual(len(head), LOG_HEAD_BYTES)
        self.assertEqual(len(tail), LOG_TAIL_BYTES)

    def test_a_log_short_enough_to_be_read_whole_has_no_tail(self):
        head, tail = self.fetch(self.make_log())

        self.assertEqual(tail, '')
        self.assertIn(self.ENDING, head)

    def test_a_log_that_cannot_be_read_is_skipped(self):
        get = mock.Mock(side_effect=requests.RequestException('boom'))

        with mock.patch('ports.management.commands.find_orphan_fallouts.requests.get', get):
            self.assertIsNone(self.command().fetch_log_content(self.LOG_URL))

    def test_the_end_time_is_read_out_of_the_tail(self):
        head, tail = self.fetch(self.make_log(filler=self.HUGE))
        details = self.command().extract_log_details(head, tail, self.LOG_URL)

        self.assertEqual(details['date'], 'Tue Aug  4 21:05:11 UTC 2026')

    def test_the_end_time_is_still_read_when_there_is_no_tail(self):
        head, tail = self.fetch(self.make_log())
        details = self.command().extract_log_details(head, tail, self.LOG_URL)

        self.assertEqual(details['date'], 'Tue Aug  4 21:05:11 UTC 2026')

    def test_everything_else_is_read_out_of_the_head(self):
        head, tail = self.fetch(self.make_log(filler=self.HUGE))
        details = self.command().extract_log_details(head, tail, self.LOG_URL)

        self.assertEqual(details['port_name'], 'textproc/py-hieroglyph')
        self.assertEqual(details['maintainer'], 'dbaio@FreeBSD.org')
        self.assertEqual(details['env'], '144i386-quarterly')
        self.assertEqual(details['version'], '2.1.0_1')
        for field, value in LOG_HEADER_VALUES.items():
            with self.subTest(field=field):
                self.assertEqual(details[field], value)

    def test_the_failing_phase_is_the_last_marker(self):
        self.assertEqual(self.command().find_failing_phase(self.make_log()),
                         'lib-depends')

    def test_a_phase_named_in_one_word_is_read_too(self):
        log = '=======================<phase: configure      >===================\n'
        self.assertEqual(self.command().find_failing_phase(log), 'configure')

    def test_every_phase_the_stylesheet_knows_is_recognised(self):
        """The dependency phases carry a hyphen, which `\\w+` used to stop at"""

        for phase in PHASE_FAMILIES:
            with self.subTest(phase=phase):
                log = f'=======================<phase: {phase:<14}>====================\n'
                self.assertEqual(self.command().find_failing_phase(log), phase)

    def test_a_log_with_no_marker_has_no_phase(self):
        self.assertIsNone(self.command().find_failing_phase(LOG_HEADER))


# The same fallout as each of the two sources reads it. The report is sent a
# second before the log is closed, and names the phase in its subject; the
# orphan finder has the end time of the log, no report, and the last phase
# marker within the head of the log.
FALLOUT_LOG_URL = ('https://pkg-status.freebsd.org/beefy19/data/144i386-quarterly/'
                   '17af07f5de95/logs/py312-hieroglyph-2.1.0_1.log')
FALLOUT_REPORT_URL = ('https://lists.freebsd.org/archives/freebsd-pkg-fallout/'
                      '2026-August/978112.html')

FROM_THE_LOG = dict(
    env='144i386-quarterly', version='2.1.0_1', category='lib-depends',
    maintainer='dbaio@FreeBSD.org', last_committer='',
    date=datetime(2026, 8, 4, 21, 5, 11, tzinfo=timezone.utc),
    build_url='https://pkg-status.freebsd.org/beefy19/build.html?'
              'mastername=144i386-quarterly&build=17af07f5de95',
    report_url='', flavor='py312', server='beefy19.nyi.freebsd.org',
    **LOG_HEADER_VALUES)

FROM_THE_REPORT = dict(FROM_THE_LOG, category='build',
                       date=datetime(2026, 8, 4, 21, 5, 10, tzinfo=timezone.utc),
                       report_url=FALLOUT_REPORT_URL)


class FalloutRecordTests(TestCase):
    """One row per build log, whichever source reaches it first"""

    @classmethod
    def setUpTestData(cls):
        cls.port = Port.objects.create(origin='textproc/py-hieroglyph',
                                       name='py-hieroglyph',
                                       maintainer='dbaio@FreeBSD.org',
                                       main_category='textproc')

    def record(self, **fields):
        return Fallout.objects.record(self.port, FALLOUT_LOG_URL, **fields)

    def test_a_log_not_seen_before_is_stored(self):
        fallout, created = self.record(**FROM_THE_REPORT)

        self.assertTrue(created)
        self.assertEqual(fallout.port, self.port)
        self.assertEqual(fallout.report_url, FALLOUT_REPORT_URL)

    def test_the_report_completes_the_row_the_orphan_finder_made(self):
        Fallout.objects.create(port=self.port, log_url=FALLOUT_LOG_URL, **FROM_THE_LOG)

        fallout, created = self.record(**FROM_THE_REPORT)

        self.assertFalse(created)
        self.assertEqual(Fallout.objects.count(), 1)
        fallout.refresh_from_db()
        self.assertEqual(fallout.report_url, FALLOUT_REPORT_URL)
        self.assertEqual(fallout.category, 'build')
        self.assertEqual(fallout.date, FROM_THE_REPORT['date'])

    def test_a_blank_does_not_wipe_what_is_stored(self):
        Fallout.objects.create(port=self.port, log_url=FALLOUT_LOG_URL, **FROM_THE_REPORT)

        fallout, _ = self.record(**dict(FROM_THE_REPORT, report_url='', package_name=''))

        fallout.refresh_from_db()
        self.assertEqual(fallout.report_url, FALLOUT_REPORT_URL)
        self.assertEqual(fallout.package_name, LOG_HEADER_VALUES['package_name'])

    def test_a_row_that_did_not_change_is_not_written(self):
        """The crawler reads the whole month again every day"""

        Fallout.objects.create(port=self.port, log_url=FALLOUT_LOG_URL, **FROM_THE_REPORT)

        with self.assertNumQueries(1):
            self.record(**FROM_THE_REPORT)

    def test_the_database_refuses_a_second_row_for_a_log(self):
        Fallout.objects.create(port=self.port, log_url=FALLOUT_LOG_URL, **FROM_THE_LOG)

        with self.assertRaises(IntegrityError), transaction.atomic():
            Fallout.objects.create(port=self.port, log_url=FALLOUT_LOG_URL,
                                   **FROM_THE_REPORT)


class OrphanSaveTests(TestCase):
    """What `find_orphan_fallouts` stores out of what it read"""

    EXTRACTED = {
        'date': 'Tue Aug  4 21:05:11 UTC 2026',
        'maintainer': 'dbaio@FreeBSD.org',
        'log_url': FALLOUT_LOG_URL,
        'build_url': FROM_THE_LOG['build_url'],
        'flavor': 'py312',
        'port_name': 'textproc/py-hieroglyph',
        'report_url': None,
        'last_committer': None,
        'error_phase': 'lib-depends',
        'version': '2.1.0_1',
        'env': '144i386-quarterly',
        **LOG_HEADER_VALUES,
    }

    @classmethod
    def setUpTestData(cls):
        cls.port = Port.objects.create(origin='textproc/py-hieroglyph',
                                       name='py-hieroglyph',
                                       maintainer='dbaio@FreeBSD.org',
                                       main_category='textproc')

    def command(self):
        return FindOrphanFallouts(stdout=StringIO())

    def test_an_orphan_log_is_stored_without_a_report(self):
        self.command().save_fallout_entry(self.EXTRACTED)

        fallout = Fallout.objects.get()
        self.assertEqual(fallout.port, self.port)
        self.assertEqual(fallout.report_url, '')
        self.assertEqual(fallout.server, 'beefy19.nyi.freebsd.org')
        self.assertEqual(fallout.date, FROM_THE_LOG['date'])
        for field, value in FROM_THE_LOG.items():
            with self.subTest(field=field):
                self.assertEqual(getattr(fallout, field), value)

    def test_a_log_the_crawler_stored_meanwhile_is_left_alone(self):
        """Its report named the phase, which the head of the log may not"""

        Fallout.objects.create(port=self.port, log_url=FALLOUT_LOG_URL, **FROM_THE_REPORT)

        self.command().save_fallout_entry(self.EXTRACTED)

        fallout = Fallout.objects.get()
        self.assertEqual(fallout.category, 'build')
        self.assertEqual(fallout.date, FROM_THE_REPORT['date'])
        self.assertEqual(fallout.report_url, FALLOUT_REPORT_URL)

    def test_a_log_already_stored_is_not_fetched(self):
        Fallout.objects.create(port=self.port, log_url=FALLOUT_LOG_URL, **FROM_THE_REPORT)
        get = mock.Mock()

        with mock.patch('ports.management.commands.find_orphan_fallouts.requests.get', get):
            self.command().process_log_url(
                FALLOUT_LOG_URL.replace('/logs/', '/logs/errors/'))

        get.assert_not_called()


class MergeDuplicateFalloutsTests(TransactionTestCase):
    """The migration merging the pairs the two sources had stored"""

    def migrate(self, target):
        executor = MigrationExecutor(connection)
        executor.migrate([('ports', target)])
        return executor.loader.project_state([('ports', target)]).apps

    def tearDown(self):
        # Leave the schema where the rest of the suite expects it.
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_the_pair_is_merged_into_the_row_with_the_report(self):
        apps = self.migrate('0008_fallout_log_details')
        Port = apps.get_model('ports', 'Port')
        Fallout = apps.get_model('ports', 'Fallout')
        port = Port.objects.create(origin='textproc/py-hieroglyph',
                                   name='py-hieroglyph',
                                   maintainer='dbaio@FreeBSD.org',
                                   main_category='textproc')

        # Made before the crawler read the log header, so short of the details
        # and the server, which its double supplies.
        Fallout.objects.create(port=port, log_url=FALLOUT_LOG_URL, **FROM_THE_LOG)
        crawled = Fallout.objects.create(
            port=port, log_url=FALLOUT_LOG_URL,
            **dict(FROM_THE_REPORT, server='',
                   **{field: '' for field in LOG_HEADER_VALUES}))
        other = Fallout.objects.create(
            port=port, log_url=FALLOUT_LOG_URL.replace('py312', 'py311'),
            **FROM_THE_REPORT)

        apps = self.migrate('0009_fallout_log_url_unique')
        Fallout = apps.get_model('ports', 'Fallout')

        self.assertEqual(Fallout.objects.count(), 2)
        self.assertTrue(Fallout.objects.filter(pk=other.pk).exists())
        kept = Fallout.objects.get(log_url=FALLOUT_LOG_URL)
        self.assertEqual(kept.pk, crawled.pk)
        self.assertEqual(kept.category, 'build')
        self.assertEqual(kept.date, FROM_THE_REPORT['date'])
        self.assertEqual(kept.server, 'beefy19.nyi.freebsd.org')
        for field, value in LOG_HEADER_VALUES.items():
            with self.subTest(field=field):
                self.assertEqual(getattr(kept, field), value)
