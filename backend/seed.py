import os
import django
import uuid

# 1. Setup Django environment first
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

# 2. Now import the models
from core.models import Merchant, Transaction, Payout

def seed():
    print("--- Starting Seed & Rescue Process ---")
    
    # --- PART A: THE RESCUE (Fix the stuck 200 payout) ---
    try:
        stuck_payout = Payout.objects.filter(id__icontains='b88f1b0a', status='PROCESSING').first()
        if stuck_payout:
            stuck_payout.status = 'COMPLETED'
            stuck_payout.save()
            print(f"✅ Success: Rescued payout {stuck_payout.id}")
        else:
            print("ℹ️ Rescue: No stuck payout found (already fixed or ID changed).")
    except Exception as e:
        print(f"⚠️ Rescue logic skipped: {e}")

    # --- PART B: THE RE-SEEDING ---
    # We use a try/except here because your previous logs showed 
    # that deleting merchants fails if they have existing payouts!
    try:
        print("Cleaning up old data...")
        # To delete merchants, we MUST delete payouts and transactions first
        # because of "Protected" foreign keys.
        Payout.objects.all().delete()
        Transaction.objects.all().delete()
        Merchant.objects.all().delete()
        print("✅ Database cleared.")
    except Exception as e:
        print(f"ℹ️ Clean-up skipped: Data is protected or already exists. ({e})")

    # Only create new merchants if they don't exist
    merchant_1, created_1 = Merchant.objects.get_or_create(name="Acme Corp")
    merchant_2, created_2 = Merchant.objects.get_or_create(name="Globex Inc")

    # Add initial credits only if we just created them
    if created_1:
        Transaction.objects.create(
            merchant=merchant_1,
            amount=50000,
            type='CREDIT',
            description='Initial simulation deposit'
        )
    
    if created_2:
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