"""
Management command to generate rent numbers for existing rents
Run with: python manage.py generate_rent_numbers
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Max
from main.models import Rent


class Command(BaseCommand):
    help = 'Generate rent_number for existing Rent records that do not have one'

    def handle(self, *args, **options):
        self.stdout.write('Generating rent numbers for existing rents...')
        
        # Get all rents without rent_number
        rents_without_number = Rent.objects.filter(rent_number__isnull=True) | Rent.objects.filter(rent_number='')
        count = rents_without_number.count()
        
        if count == 0:
            self.stdout.write(self.style.SUCCESS('No rents need rent numbers.'))
            return
        
        self.stdout.write(f'Found {count} rents without rent numbers.')
        
        with transaction.atomic():
            for rent in rents_without_number:
                # Manually generate rent_number since save() only works for new records
                last_number = Rent.objects.filter(
                    owner=rent.owner,
                    property=rent.property
                ).exclude(rent_sequence_number__isnull=True).aggregate(
                    Max('rent_sequence_number')
                )['rent_sequence_number__max'] or 0
                
                rent.rent_sequence_number = last_number + 1
                
                # Format: RENT-OWNER_ID-PROPERTY_ID-SEQUENCE
                padded_seq = str(rent.rent_sequence_number).zfill(4)
                property_id = rent.property.id if rent.property else 0
                base_rent_number = f"RENT-{rent.owner.id}-{property_id}-{padded_seq}"
                
                # Check for duplicates
                counter = 0
                rent.rent_number = base_rent_number
                while Rent.objects.filter(rent_number=rent.rent_number).exclude(id=rent.id).exists():
                    counter += 1
                    rent.rent_number = f"{base_rent_number}-{counter}"
                
                rent.save()
                self.stdout.write(
                    self.style.SUCCESS(f'Generated rent_number {rent.rent_number} for Rent ID {rent.id}')
                )
        
        self.stdout.write(self.style.SUCCESS(f'Successfully generated {count} rent numbers.'))
