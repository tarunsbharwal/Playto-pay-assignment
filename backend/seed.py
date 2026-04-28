import os
import django

# 1. Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

# 2. Import the models
from core.models import Merchant, Transaction, Payout

def seed():
    print("--- 🚀 Starting Final Hard Reset ---")
    
    try:
        print("Cleaning up old data...")
        
        # ✅ STEP 1: Delete Transactions first (they are the 'children')
        Transaction.objects.all().delete() 
        
        # ✅ STEP 2: Now Payouts can be deleted safely
        Payout.objects.all().delete()
        
        # ✅ STEP 3: Finally delete the Merchants
        Merchant.objects.all().delete()
        
        print("✅ Database cleared successfully.")

        # 3. FRESH CREATION
        merchant_1 = Merchant.objects.create(name="Acme Corp")
        merchant_2 = Merchant.objects.create(name="Globex Inc")

        # Acme Corp: ₹500.00 (50000 paise)
        Transaction.objects.create(
            merchant=merchant_1,
            amount=50000,
            type='CREDIT',
            description='Initial simulation deposit'
        )
        
        # Globex Inc: ₹2500.00 (250000 paise)
        Transaction.objects.create(
            merchant=merchant_2,
            amount=250000,
            type='CREDIT',
            description='Initial simulation deposit'
        )

        print(f"✅ Reset Successful! Acme: {merchant_1.balance/100} | Globex: {merchant_2.balance/100}")

    except Exception as e:
        print(f"❌ Clean-up failed: {e}")

    print("--- 🏁 Reset Process Finished ---")

if __name__ == '__main__':
    seed()