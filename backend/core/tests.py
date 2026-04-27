from django.test import TransactionTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework import status
import uuid
import threading
from django.db import connection

from .models import Merchant, Payout, Transaction

class PayoutConcurrencyTest(TransactionTestCase):
    # CHANGED: Must use TransactionTestCase so threads can handle their own locks
    def setUp(self):
        self.merchant = Merchant.objects.create(name="Test Merchant")
        # Give merchant 100 rupees (10000 paise)
        Transaction.objects.create(
            merchant=self.merchant,
            amount=10000,
            type='CREDIT',
            description='Initial deposit'
        )

    def test_concurrent_payouts_do_not_overdraw(self):
        """
        Simulate two concurrent 60 rupee payout requests.
        Only one should succeed.
        """
        client1 = APIClient()
        client2 = APIClient()
        
        url = '/api/v1/payouts/'
        # CHANGED: Updated 'amount' to 'amount_paise' to match the serializer
        payload1 = {'amount_paise': 6000, 'bank_account_id': 'bank_1'}
        payload2 = {'amount_paise': 6000, 'bank_account_id': 'bank_2'}
        
        headers1 = {'HTTP_X_MERCHANT_ID': str(self.merchant.id), 'HTTP_IDEMPOTENCY_KEY': str(uuid.uuid4())}
        headers2 = {'HTTP_X_MERCHANT_ID': str(self.merchant.id), 'HTTP_IDEMPOTENCY_KEY': str(uuid.uuid4())}

        response1 = None
        response2 = None

        def req1():
            nonlocal response1
            # We must close old connections in threads when using Django tests
            connection.close()
            response1 = client1.post(url, payload1, format='json', **headers1)
            
        def req2():
            nonlocal response2
            connection.close()
            response2 = client2.post(url, payload2, format='json', **headers2)

        t1 = threading.Thread(target=req1)
        t2 = threading.Thread(target=req2)
        
        t1.start()
        t2.start()
        
        t1.join()
        t2.join()

        # One should be 201 Created, the other 400 Bad Request
        status_codes = {response1.status_code, response2.status_code}
        self.assertIn(status.HTTP_201_CREATED, status_codes)
        self.assertIn(status.HTTP_400_BAD_REQUEST, status_codes)

        # Refresh merchant balance
        self.merchant.refresh_from_db()
        self.assertEqual(self.merchant.balance, 4000) # 10000 - 6000
        self.assertEqual(Payout.objects.count(), 1)


class PayoutIdempotencyTest(TestCase):
    # Standard TestCase is fine here since it executes sequentially
    def setUp(self):
        self.client = APIClient()
        self.merchant = Merchant.objects.create(name="Test Merchant")
        Transaction.objects.create(
            merchant=self.merchant,
            amount=10000,
            type='CREDIT'
        )
        self.url = '/api/v1/payouts/'

    def test_idempotency_returns_same_response(self):
        idemp_key = str(uuid.uuid4())
        # CHANGED: Updated 'amount' to 'amount_paise'
        payload = {'amount_paise': 2000, 'bank_account_id': 'bank_test'}
        headers = {'HTTP_X_MERCHANT_ID': str(self.merchant.id), 'HTTP_IDEMPOTENCY_KEY': idemp_key}
        
        # First request
        resp1 = self.client.post(self.url, payload, format='json', **headers)
        self.assertEqual(resp1.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Payout.objects.count(), 1)
        
        # Second request with identical key
        resp2 = self.client.post(self.url, payload, format='json', **headers)
        
        # Should return 200 OK (not 201) and same data, no new payout
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.assertEqual(Payout.objects.count(), 1)
        self.assertEqual(resp1.data['id'], resp2.data['id'])
