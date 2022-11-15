# Copyright (c) 2020-2022 Danilo G. Baio <dbaio@FreeBSD.org>
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

from django.contrib import admin
from ports.models import Category, Port, Fallout, Server


class PortAdmin(admin.ModelAdmin):
    ordering = ['origin']
    search_fields = ['name', 'origin', 'maintainer']
    list_display = ['origin', 'maintainer', 'www']
    list_filter = ['main_category']


class CategoryAdmin(admin.ModelAdmin):
    ordering = ['name']
    search_fields = ['name']


class FalloutAdmin(admin.ModelAdmin):
    list_display = ('port', 'maintainer', 'version', 'env', 'category', 'date')
    ordering = ['-date']
    readonly_fields = ['port']
    search_fields = ['env', 'maintainer', 'log_url']
    list_filter = ['date', 'env', 'category']
    date_hierarchy = 'date'
    actions_selection_counter = True
    actions_on_top = True
    actions_on_bottom = True


class ServerAdmin(admin.ModelAdmin):
    ordering = ['name']
    search_fields = ['name']


admin.site.register(Port, PortAdmin)
admin.site.register(Category, CategoryAdmin)
admin.site.register(Fallout, FalloutAdmin)
admin.site.register(Server, ServerAdmin)

admin.site.site_header = "Ports Fallout Admin"
admin.site.site_title = "Admin Ports Fallout"

