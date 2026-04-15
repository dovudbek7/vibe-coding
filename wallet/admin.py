from django.contrib import admin

from .models import Category, Transaction


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'icon')
    search_fields = ('name', 'user__username', 'user__email')


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'amount', 'type', 'category', 'created_at')
    list_filter = ('type', 'category', 'created_at')
    search_fields = ('title', 'note', 'user__username', 'user__email')

# Register your models here.
