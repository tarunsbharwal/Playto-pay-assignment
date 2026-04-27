import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1';

const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
});

export const fetchMerchants = () => api.get('/merchants/');

export const fetchMerchant = (id) => api.get(`/merchants/${id}/`);

export const fetchTransactions = (merchantId) =>
  api.get(`/merchants/${merchantId}/transactions/`);

export const fetchPayouts = (merchantId) =>
  api.get(`/merchants/${merchantId}/payouts/`);

export const createPayout = (merchantId, idempotencyKey, amountPaise, bankAccountId) =>
  api.post(
    '/payouts/',
    { amount_paise: amountPaise, bank_account_id: bankAccountId },
    {
      headers: {
        'X-Merchant-Id': merchantId,
        'Idempotency-Key': idempotencyKey,
      },
    }
  );

export default api;
