import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from core.models import Merchant, Transaction
import uuid

def seed():
    print("Seeding database...")
    Merchant.objects.all().delete()
    Transaction.objects.all().delete()
    
    # Create merchants
    merchant_1 = Merchant.objects.create(name="Acme Corp")
    merchant_2 = Merchant.objects.create(name="Globex Inc")
    
    # Add credits
    # Acme Corp gets 500.00 INR (50000 paise)
    Transaction.objects.create(
        merchant=merchant_1,
        amount=50000,
        type='CREDIT',
        description='Initial simulation deposit'
    )
    
    # Globex Inc gets 2500.00 INR (250000 paise)
    Transaction.objects.create(
        merchant=merchant_2,
        amount=250000,
        type='CREDIT',
        description='Initial simulation deposit'
    )
    
    print(f"Merchant 1: {merchant_1.name} (ID: {merchant_1.id}) - Balance: {merchant_1.balance/100} INR")
    print(f"Merchant 2: {merchant_2.name} (ID: {merchant_2.id}) - Balance: {merchant_2.balance/100} INR")
    print("Done!")

if __name__ == '__main__':
    seed()
