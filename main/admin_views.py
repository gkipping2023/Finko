from django import forms
from django.shortcuts import render, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.http import JsonResponse
from main.form_labels import FORM_LABELS, FORM_HELP_TEXTS, FORM_PLACEHOLDERS
import json

@staff_member_required
def form_labels_admin(request):
    """Admin view to manage form labels"""
    context = {
        'forms': FORM_LABELS.keys(),
        'form_labels': FORM_LABELS,
        'form_help_texts': FORM_HELP_TEXTS,
        'form_placeholders': FORM_PLACEHOLDERS,
    }
    return render(request, 'admin/form_labels_admin.html', context)

@staff_member_required
def get_form_data(request, form_name):
    """API endpoint to get form data as JSON"""
    if form_name not in FORM_LABELS:
        return JsonResponse({'error': 'Form not found'}, status=404)
    
    data = {
        'labels': FORM_LABELS.get(form_name, {}),
        'help_texts': FORM_HELP_TEXTS.get(form_name, {}),
        'placeholders': FORM_PLACEHOLDERS.get(form_name, {}),
    }
    return JsonResponse(data)

@staff_member_required
def export_form_labels(request):
    """Export all form labels as JSON"""
    data = {
        'labels': FORM_LABELS,
        'help_texts': FORM_HELP_TEXTS,
        'placeholders': FORM_PLACEHOLDERS
    }
    
    response = JsonResponse(data, json_dumps_params={'indent': 2, 'ensure_ascii': False})
    response['Content-Disposition'] = 'attachment; filename="form_labels.json"'
    return response