import uuid
from django.core.management.base import BaseCommand
from core.models import Merchant, Transaction


class Command(BaseCommand):
    help = 'Seed the database with test merchants and credit history'

    def handle(self, *args, **options):
        self.stdout.write('Seeding database...\n')

        # Clear existing data
        Transaction.objects.all().delete()
        from core.models import Payout
        Payout.objects.all().delete()
        Merchant.objects.all().delete()

        # Create merchants
        merchants_data = [
            {
                'name': 'Acme Design Studio',
                'credits': [
                    (5000000, 'Invoice #INV-001 — Website redesign for ClientCo'),
                    (3200000, 'Invoice #INV-002 — Brand identity package'),
                    (1500000, 'Invoice #INV-003 — Monthly retainer — March 2026'),
                    (2800000, 'Invoice #INV-004 — UI/UX audit for StartupXYZ'),
                ],
            },
            {
                'name': 'Ravi Kumar Freelance',
                'credits': [
                    (2500000, 'Invoice #FK-101 — React development — Sprint 1'),
                    (1800000, 'Invoice #FK-102 — API integration project'),
                    (750000, 'Invoice #FK-103 — Bug fixes and maintenance'),
                ],
            },
            {
                'name': 'Zenith Digital Agency',
                'credits': [
                    (10000000, 'Invoice #ZD-2001 — E-commerce platform build'),
                    (4500000, 'Invoice #ZD-2002 — Mobile app development Phase 1'),
                    (3000000, 'Invoice #ZD-2003 — SEO and marketing automation'),
                    (2200000, 'Invoice #ZD-2004 — Cloud infrastructure setup'),
                    (1600000, 'Invoice #ZD-2005 — Monthly support — Q1 2026'),
                ],
            },
        ]

        for merchant_data in merchants_data:
            merchant = Merchant.objects.create(name=merchant_data['name'])
            self.stdout.write(f'  Created merchant: {merchant.name} ({merchant.id})')

            total = 0
            for amount, description in merchant_data['credits']:
                Transaction.objects.create(
                    merchant=merchant,
                    amount=amount,
                    type='CREDIT',
                    description=description,
                )
                total += amount

            self.stdout.write(f'    Added {len(merchant_data["credits"])} credits, '
                              f'total: ₹{total / 100:,.2f}\n')

        self.stdout.write(self.style.SUCCESS(
            '\nSeeding complete! Created 3 merchants with credit history.'
        ))
        self.stdout.write('\nMerchant balances:')
        for m in Merchant.objects.all():
            self.stdout.write(f'  {m.name}: ₹{m.balance / 100:,.2f}')
