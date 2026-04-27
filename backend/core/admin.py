from django.contrib import admin
from .models import Merchant, Payout, Transaction


@admin.register(Merchant)
class MerchantAdmin(admin.ModelAdmin):
    list_display = ('name', 'id', 'balance', 'created_at')
    readonly_fields = ('id', 'created_at')


@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    list_display = ('id', 'merchant', 'amount', 'status', 'attempts', 'created_at')
    list_filter = ('status',)
    readonly_fields = ('id', 'created_at', 'updated_at')


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'merchant', 'amount', 'type', 'description', 'created_at')
    list_filter = ('type',)
    readonly_fields = ('id', 'created_at')
