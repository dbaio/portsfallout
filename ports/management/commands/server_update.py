# Copyright (c) 2020 Danilo G. Baio <dbaio@bsd.com.br>
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

from django.core.management.base import BaseCommand, CommandError
from ports.models import Server, Fallout

from django.utils import timezone as dtz

import parser
import dns.resolver


class Command(BaseCommand):
    help = 'Update DNS values of the pkg-fallout servers'

    def add_arguments(self, parser):

        parser.add_argument('period',
                            nargs='?', 
                            type=int, 
                            help='Query entries from the last X days (default: 90)',)

    def handle(self, *args, **options):

        if not options['period']:
            period = 90
        else:
            period = options['period']

        period_date = dtz.make_aware(dtz.datetime.today() - dtz.timedelta(days=period))
        Servers = Fallout.objects.filter(date__gte=period_date).values('server').distinct().order_by('server')

        for srv in Servers:
            if srv['server']:
                self.stdout.write(f"{srv['server']}")

                try:
                    dns_v4 = dns.resolver.query(srv['server'], 'A')
                except:
                    dns_v4 = False

                try:
                    dns_v6 = dns.resolver.query(srv['server'], 'AAAA')
                except:
                    dns_v6 = False

                if dns_v4:
                    self.stdout.write(self.style.SUCCESS('  Has IPv4 address'))
                else:
                    self.stdout.write(self.style.ERROR('  IPv4 address not found'))

                if dns_v6:
                    self.stdout.write(self.style.SUCCESS('  Has IPv6 address'))
                else:
                    self.stdout.write(self.style.ERROR('  IPv6 address not found'))


                try:
                    db_srv = Server.objects.get(name=srv['server'])
                except:
                    db_srv = None    

                if db_srv:
                    if db_srv.v4 != bool(dns_v4) or db_srv.v6 != bool(dns_v6):
                        db_srv.v4 = bool(dns_v4)
                        db_srv.v6 = bool(dns_v6)
                        db_srv.save()
                else:
                    db_srv = Server.objects.get_or_create(name=srv['server'],
                                    v4 = bool(dns_v4),
                                    v6 = bool(dns_v6))[0]