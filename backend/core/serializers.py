from rest_framework import serializers
from django.db.models import Sum
from django.db.models.functions import Coalesce
from .models import Merchant, Payout, Transaction


class MerchantSerializer(serializers.ModelSerializer):
    balance = serializers.IntegerField(read_only=True)
    held_balance = serializers.SerializerMethodField()

    class Meta:
        model = Merchant
        fields = ['id', 'name', 'email', 'balance', 'held_balance', 'created_at']

    def get_held_balance(self, obj):
        """Sum of payouts in PENDING or PROCESSING — funds that are locked but not settled."""
        aggs = obj.payouts.filter(
            status__in=[Payout.Status.PENDING, Payout.Status.PROCESSING]
        ).aggregate(
            held=Coalesce(Sum('amount'), 0)
        )
        return aggs['held']


class PayoutCreateSerializer(serializers.Serializer):
    """Input serializer for POST /api/v1/payouts/. Matches the API spec."""
    amount_paise = serializers.IntegerField(min_value=1)
    bank_account_id = serializers.CharField(max_length=255)


class PayoutSerializer(serializers.ModelSerializer):
    """Output serializer for payout responses."""
    amount_paise = serializers.IntegerField(source='amount', read_only=True)

    class Meta:
        model = Payout
        fields = [
            'id', 'merchant', 'amount_paise', 'bank_account_id',
            'status', 'idempotency_key', 'attempts',
            'processing_started_at', 'created_at', 'updated_at',
        ]


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = ['id', 'amount', 'type', 'payout', 'description', 'created_at']
