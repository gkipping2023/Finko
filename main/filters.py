import django_filters
from .models import Transaction, Properties, User

class TransactionFilter(django_filters.FilterSet):
	type = django_filters.ChoiceFilter(
		field_name='type',
		choices=lambda: Transaction._meta.get_field('type').choices,
		label='Tipo',
		empty_label='All'
	)
	tenant = django_filters.ModelChoiceFilter(
		queryset=User.objects.filter(role='T'),
		label='Inquilino',
		empty_label='All'
	)
	property = django_filters.ModelChoiceFilter(
		queryset=Properties.objects.all(),
		label='Propiedad',
		empty_label='All'
	)
	date_range = django_filters.CharFilter(method='filter_date_range', label='Date Range')

	class Meta:
		model = Transaction
		fields = ['type', 'tenant', 'property', 'date_range']

	def filter_date_range(self, queryset, name, value):
		if value:
			try:
				# Accepts 'YYYY-MM-DD - YYYY-MM-DD' or 'YYYY/MM/DD - YYYY/MM/DD'
				import re
				match = re.match(r"(\d{4}-\d{2}-\d{2})\s*-\s*(\d{4}-\d{2}-\d{2})", value)
				if match:
					start, end = match.groups()
					return queryset.filter(created_at__date__gte=start, created_at__date__lte=end)
			except Exception:
				return queryset
		return queryset
