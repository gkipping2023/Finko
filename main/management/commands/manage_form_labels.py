from django.core.management.base import BaseCommand
from main.form_labels import FORM_LABELS, FORM_HELP_TEXTS, FORM_PLACEHOLDERS
import json

class Command(BaseCommand):
    help = 'Manage form labels configuration'

    def add_arguments(self, parser):
        parser.add_argument(
            '--list',
            action='store_true',
            help='List all current form labels',
        )
        parser.add_argument(
            '--form',
            type=str,
            help='Specify form name to view/edit',
        )
        parser.add_argument(
            '--export',
            type=str,
            help='Export form labels to JSON file',
        )
        parser.add_argument(
            '--import',
            type=str,
            dest='import_file',
            help='Import form labels from JSON file',
        )

    def handle(self, *args, **options):
        if options['list']:
            self.list_forms()
        elif options['form']:
            self.show_form_details(options['form'])
        elif options['export']:
            self.export_labels(options['export'])
        elif options['import_file']:
            self.import_labels(options['import_file'])
        else:
            self.stdout.write(
                self.style.ERROR('Please specify an action: --list, --form, --export, or --import')
            )

    def list_forms(self):
        """List all available forms and their field counts"""
        self.stdout.write(self.style.SUCCESS('Available Forms:'))
        self.stdout.write('-' * 50)
        
        for form_name in FORM_LABELS.keys():
            field_count = len(FORM_LABELS[form_name])
            help_count = len(FORM_HELP_TEXTS.get(form_name, {}))
            placeholder_count = len(FORM_PLACEHOLDERS.get(form_name, {}))
            
            self.stdout.write(f'{form_name}:')
            self.stdout.write(f'  - Labels: {field_count} fields')
            self.stdout.write(f'  - Help texts: {help_count} fields')
            self.stdout.write(f'  - Placeholders: {placeholder_count} fields')
            self.stdout.write('')

    def show_form_details(self, form_name):
        """Show detailed information for a specific form"""
        if form_name not in FORM_LABELS:
            self.stdout.write(
                self.style.ERROR(f'Form "{form_name}" not found. Use --list to see available forms.')
            )
            return

        self.stdout.write(self.style.SUCCESS(f'Details for {form_name}:'))
        self.stdout.write('=' * 60)

        # Show labels
        self.stdout.write(self.style.WARNING('LABELS:'))
        for field, label in FORM_LABELS[form_name].items():
            self.stdout.write(f'  {field}: "{label}"')

        # Show help texts
        if form_name in FORM_HELP_TEXTS:
            self.stdout.write('\n' + self.style.WARNING('HELP TEXTS:'))
            for field, help_text in FORM_HELP_TEXTS[form_name].items():
                self.stdout.write(f'  {field}: "{help_text}"')

        # Show placeholders
        if form_name in FORM_PLACEHOLDERS:
            self.stdout.write('\n' + self.style.WARNING('PLACEHOLDERS:'))
            for field, placeholder in FORM_PLACEHOLDERS[form_name].items():
                self.stdout.write(f'  {field}: "{placeholder}"')

    def export_labels(self, filename):
        """Export all form labels to a JSON file"""
        data = {
            'labels': FORM_LABELS,
            'help_texts': FORM_HELP_TEXTS,
            'placeholders': FORM_PLACEHOLDERS
        }
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self.stdout.write(
                self.style.SUCCESS(f'Form labels exported to {filename}')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error exporting labels: {e}')
            )

    def import_labels(self, filename):
        """Import form labels from a JSON file"""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # This would require modifying the form_labels.py file
            # For now, just show what would be imported
            self.stdout.write(
                self.style.SUCCESS(f'Labels loaded from {filename}:')
            )
            
            if 'labels' in data:
                self.stdout.write(f'  - {len(data["labels"])} forms with labels')
            if 'help_texts' in data:
                self.stdout.write(f'  - {len(data["help_texts"])} forms with help texts')
            if 'placeholders' in data:
                self.stdout.write(f'  - {len(data["placeholders"])} forms with placeholders')
                
            self.stdout.write(
                self.style.WARNING('Note: To apply these changes, you need to manually update main/form_labels.py')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error importing labels: {e}')
            )