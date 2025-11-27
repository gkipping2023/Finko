"""
Management command to mark existing users as having accepted privacy policy and terms
Run with: python manage.py accept_privacy_for_existing_users
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from main.models import User


class Command(BaseCommand):
    help = 'Mark all existing users as having accepted privacy policy and terms (for test/development users)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--yes',
            action='store_true',
            help='Skip confirmation prompt',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING(
            '\n' + '='*70 + '\n'
            'ATENCIÓN: Este comando marcará a TODOS los usuarios existentes como\n'
            'que han aceptado la Política de Privacidad y Términos y Condiciones.\n'
            '\n'
            'Solo ejecute este comando si:\n'
            '1. Los usuarios actuales son de prueba/desarrollo, o\n'
            '2. Ha obtenido consentimiento retroactivo de todos los usuarios\n'
            '\n'
            'Conforme a la Ley 81, debe obtener consentimiento explícito.\n'
            '=' * 70 + '\n'
        ))
        
        users_without_consent = User.objects.filter(privacy_policy_accepted=False)
        count = users_without_consent.count()
        
        if count == 0:
            self.stdout.write(self.style.SUCCESS('Todos los usuarios ya tienen consentimientos registrados.'))
            return
        
        self.stdout.write(f'\nUsuarios sin consentimiento: {count}')
        
        # Show users
        self.stdout.write('\nUsuarios afectados:')
        for user in users_without_consent[:10]:  # Show first 10
            self.stdout.write(f'  - {user.email} ({user.full_name}) - Registrado: {user.date_joined}')
        
        if count > 10:
            self.stdout.write(f'  ... y {count - 10} más')
        
        # Confirmation
        if not options['yes']:
            confirm = input('\n¿Continuar? Escriba "SI" para confirmar: ')
            if confirm != 'SI':
                self.stdout.write(self.style.ERROR('Operación cancelada.'))
                return
        
        # Update users
        now = timezone.now()
        updated_count = 0
        
        for user in users_without_consent:
            user.privacy_policy_accepted = True
            user.privacy_policy_accepted_date = now
            user.terms_accepted = True
            user.terms_accepted_date = now
            user.data_retention_consent = True
            user.marketing_consent = False  # Default to no marketing
            user.save()
            updated_count += 1
            
            self.stdout.write(
                self.style.SUCCESS(f'✓ Actualizado: {user.email}')
            )
        
        self.stdout.write('\n' + '='*70)
        self.stdout.write(
            self.style.SUCCESS(
                f'\n✓ {updated_count} usuarios actualizados exitosamente.\n'
                f'  Fecha de consentimiento: {now.strftime("%d/%m/%Y %H:%M:%S")}\n'
            )
        )
        self.stdout.write('='*70 + '\n')
        
        # Recommendations
        self.stdout.write(self.style.WARNING(
            '\nRECOMENDACIONES:\n'
            '1. Envíe un email a todos los usuarios informándoles sobre la Política de Privacidad\n'
            '2. Documente esta acción para auditorías de cumplimiento\n'
            '3. Los nuevos usuarios deberán aceptar explícitamente al registrarse\n'
        ))
