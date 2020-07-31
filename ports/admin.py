from django.contrib import admin
from ports.models import Category, Port, Fallout


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


admin.site.register(Port, PortAdmin)
admin.site.register(Category, CategoryAdmin)
admin.site.register(Fallout, FalloutAdmin)

admin.site.site_header = "Ports Fallout Admin"
admin.site.site_title = "Admin Ports Fallout"

