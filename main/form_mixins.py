from django import forms
from .form_labels import FORM_LABELS, FORM_HELP_TEXTS, FORM_PLACEHOLDERS

class CustomizableFormMixin:
    """
    Mixin to automatically apply custom labels, help texts, and placeholders
    to Django forms based on configuration in form_labels.py
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_custom_labels()
        self.apply_custom_help_texts()
        self.apply_custom_placeholders()
    
    def apply_custom_labels(self):
        """Apply custom labels from FORM_LABELS configuration"""
        form_name = self.__class__.__name__
        if form_name in FORM_LABELS:
            labels = FORM_LABELS[form_name]
            for field_name, label in labels.items():
                if field_name in self.fields:
                    self.fields[field_name].label = label
    
    def apply_custom_help_texts(self):
        """Apply custom help texts from FORM_HELP_TEXTS configuration"""
        form_name = self.__class__.__name__
        if form_name in FORM_HELP_TEXTS:
            help_texts = FORM_HELP_TEXTS[form_name]
            for field_name, help_text in help_texts.items():
                if field_name in self.fields:
                    self.fields[field_name].help_text = help_text
    
    def apply_custom_placeholders(self):
        """Apply custom placeholders from FORM_PLACEHOLDERS configuration"""
        form_name = self.__class__.__name__
        if form_name in FORM_PLACEHOLDERS:
            placeholders = FORM_PLACEHOLDERS[form_name]
            for field_name, placeholder in placeholders.items():
                if field_name in self.fields:
                    # Only add placeholder if widget supports it
                    widget = self.fields[field_name].widget
                    if hasattr(widget, 'attrs'):
                        widget.attrs['placeholder'] = placeholder

class BaseCustomForm(CustomizableFormMixin, forms.Form):
    """Base form class with customizable labels"""
    pass

class BaseCustomModelForm(CustomizableFormMixin, forms.ModelForm):
    """Base model form class with customizable labels"""
    pass

class BaseCustomUserCreationForm(CustomizableFormMixin, forms.Form):
    """Base user creation form class with customizable labels"""
    pass