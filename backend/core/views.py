from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db import transaction
from django.db.models import Sum, Q
from django.db.models.functions import Coalesce
from django.utils import timezone
from datetime import timedelta
import logging

from .models import Merchant, Payout, Transaction
from .serializers import (
    MerchantSerializer, PayoutSerializer,
    PayoutCreateSerializer, TransactionSerializer
)
from .tasks import process_payout_task

logger = logging.getLogger(__name__)


class MerchantViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Merchant.objects.all()
    serializer_class = MerchantSerializer

    @action(detail=True, methods=['get'])
    def transactions(self, request, pk=None):
        merchant = self.get_object()
        transactions = merchant.transactions.all().order_by('-created_at')
        page = self.paginate_queryset(transactions)
        if page is not None:
            serializer = TransactionSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = TransactionSerializer(transactions, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def payouts(self, request, pk=None):
        merchant = self.get_object()
        payouts = merchant.payouts.all().order_by('-created_at')
        page = self.paginate_queryset(payouts)
        if page is not None:
            serializer = PayoutSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = PayoutSerializer(payouts, many=True)
        return Response(serializer.data)


class PayoutViewSet(viewsets.ViewSet):
    """
    POST /api/v1/payouts/
    Headers: X-Merchant-Id (UUID), Idempotency-Key (UUID)
    Body: { "amount_paise": int, "bank_account_id": str }

    Concurrency model:
        1. SELECT FOR UPDATE on the Merchant row — serializes all payout
           requests for the same merchant.
        2. Compute balance via DB aggregation INSIDE the locked transaction.
        3. Create Payout + DEBIT Transaction atomically.
        4. The second concurrent request blocks on step 1 until the first
           commits, then sees the updated balance and gets rejected.

    Idempotency model:
        - Check for existing payout with same (merchant, idempotency_key)
          INSIDE the locked transaction.
        - If found within 24h, return the cached response (200 OK).
        - If not found, create new payout (201 Created).
        - The DB UniqueConstraint is the final safety net against duplicates.
    """

    def create(self, request):
        merchant_id = request.headers.get('X-Merchant-Id')
        idempotency_key = request.headers.get('Idempotency-Key')

        if not merchant_id:
            return Response(
                {'error': 'X-Merchant-Id header is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not idempotency_key:
            return Response(
                {'error': 'Idempotency-Key header is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate input body
        input_serializer = PayoutCreateSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        amount_paise = input_serializer.validated_data['amount_paise']
        bank_account_id = input_serializer.validated_data['bank_account_id']

        # 24-hour expiry window for idempotency keys
        cutoff_time = timezone.now() - timedelta(hours=24)

        try:
            with transaction.atomic():
                # ┌─────────────────────────────────────────────────────────┐
                # │ CRITICAL SECTION: SELECT FOR UPDATE on the Merchant    │
                # │ This acquires a PostgreSQL row-level exclusive lock.   │
                # │ Any concurrent request for the same merchant BLOCKS    │
                # │ here until this transaction commits or rolls back.     │
                # └─────────────────────────────────────────────────────────┘
                merchant = Merchant.objects.select_for_update().get(id=merchant_id)

                # Idempotency check — inside the lock so in-flight
                # duplicates are serialized
                existing_payout = Payout.objects.filter(
                    merchant=merchant,
                    idempotency_key=idempotency_key,
                    created_at__gte=cutoff_time,
                ).first()

                if existing_payout:
                    # Return exact same response — no duplicate created
                    return Response(
                        PayoutSerializer(existing_payout).data,
                        status=status.HTTP_200_OK
                    )

                # Compute available balance using DB-level aggregation.
                # This runs INSIDE the locked transaction, so no other
                # request can modify the balance between check and deduct.
                aggs = Transaction.objects.filter(merchant=merchant).aggregate(
                    total_credits=Coalesce(
                        Sum('amount', filter=Q(type=Transaction.Type.CREDIT)),
                        0
                    ),
                    total_debits=Coalesce(
                        Sum('amount', filter=Q(type=Transaction.Type.DEBIT)),
                        0
                    ),
                )
                balance = aggs['total_credits'] - aggs['total_debits']

                if balance < amount_paise:
                    return Response(
                        {
                            'error': 'Insufficient funds',
                            'available_paise': balance,
                            'requested_paise': amount_paise,
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Create the payout record
                payout = Payout.objects.create(
                    merchant=merchant,
                    amount=amount_paise,
                    bank_account_id=bank_account_id,
                    idempotency_key=idempotency_key,
                    status=Payout.Status.PENDING,
                )

                # Immediately create a DEBIT transaction to hold the funds.
                # This is inside the same atomic block, so the balance
                # deduction is guaranteed to happen with the payout creation.
                Transaction.objects.create(
                    merchant=merchant,
                    amount=amount_paise,
                    type=Transaction.Type.DEBIT,
                    payout=payout,
                    description=f"Payout hold — {payout.id}",
                )

            # ── Outside atomic block ──
            # Enqueue background processing via Celery
            process_payout_task.delay(str(payout.id))

            return Response(
                PayoutSerializer(payout).data,
                status=status.HTTP_201_CREATED
            )

        except Merchant.DoesNotExist:
            return Response(
                {'error': 'Merchant not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Payout creation error: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
