import os
import django
import uuid

# 1. Setup Django environment first
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

# 2. Now import the models
from core.models import Merchant, Transaction, Payout

def seed():
    print("--- Starting Hard Reset & Seed ---")
    
    # --- PART A: THE RESCUE (Optional) ---
    try:
        stuck_payout = Payout.objects.filter(id__icontains='b88f1b0a', status='PROCESSING').first()
        if stuck_payout:
            stuck_payout.status = 'COMPLETED'
            stuck_payout.save()
            print(f"✅ Success: Rescued legacy payout.")
    except:
        pass

    # --- PART B: THE RE-SEEDING (Corrected Order) ---
    try:
        print("Cleaning up old data...")
        # 1. Delete Transactions first (They reference both Payouts and Merchants)
        Transaction.objects.all().delete() 
        # 2. Delete Payouts second (They reference Merchants)
        Payout.objects.all().delete()
        # 3. Delete Merchants last
        Merchant.objects.all().delete()
        print("✅ Database cleared successfully.")
    except Exception as e:
        print(f"❌ Clean-up failed: {e}")
        return

    # --- PART C: FRESH CREATION ---
    # Since we successfully cleared the tables, we use .create()
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

    print(f"Merchant 1: {merchant_1.name} - Balance: {merchant_1.balance/100} INR")
    print(f"Merchant 2: {merchant_2.name} - Balance: {merchant_2.balance/100} INR")
    print("--- Done! ---")

if __name__ == '__main__':
    seed()