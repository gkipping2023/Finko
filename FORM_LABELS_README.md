# Form Labels Customization System

This system allows you to easily customize all form labels, help texts, and placeholders in your Django application without modifying individual form files.

## 📁 Files Created

1. **`main/form_labels.py`** - Configuration file with all customizable text
2. **`main/form_mixins.py`** - Mixin classes for automatic label application
3. **`main/management/commands/manage_form_labels.py`** - Management command for label administration
4. **`main/admin_views.py`** - Admin views for web-based label management
5. **`main/templates/admin/form_labels_admin.html`** - Admin interface template

## 🚀 How to Use

### Method 1: Edit Configuration File (Recommended)

1. **Open `main/form_labels.py`**
2. **Find your form in `FORM_LABELS`**
3. **Edit the labels directly:**

```python
'NewUserForm': {
    'first_name': 'Nombre Completo',  # Changed from 'Nombre'
    'email': 'Dirección de Email',    # Changed from 'Correo Electrónico'
    # ... other fields
},
```

4. **Save the file** - Changes apply immediately!

### Method 2: Management Command

List all forms and their labels:
```bash
python manage.py manage_form_labels --list
```

View specific form details:
```bash
python manage.py manage_form_labels --form NewUserForm
```

Export labels to JSON:
```bash
python manage.py manage_form_labels --export labels_backup.json
```

### Method 3: Admin Interface (Future Enhancement)

Access the admin interface at `/admin/form-labels/` (requires staff permissions)

## 📝 Available Configuration Types

### 1. Labels (Required Field Names)
```python
FORM_LABELS = {
    'FormName': {
        'field_name': 'Display Label',
    }
}
```

### 2. Help Texts (Additional Information)
```python
FORM_HELP_TEXTS = {
    'FormName': {
        'field_name': 'Helpful information for users',
    }
}
```

### 3. Placeholders (Input Examples)
```python
FORM_PLACEHOLDERS = {
    'FormName': {
        'field_name': 'Example: user@domain.com',
    }
}
```

## 🔧 Form Integration

All forms have been updated to use the mixin system:

### Before:
```python
class MyForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].label = 'Nombre'  # Manual label setting
```

### After:
```python
class MyForm(BaseCustomModelForm):  # Uses mixin
    # Labels automatically applied from form_labels.py
    pass
```

## 📋 Available Forms

- **NewUserForm** - User registration
- **UpdateUserForm** - User profile updates
- **AddPropertyForm** - Property creation
- **NewRentForm** - Rental agreement creation
- **RenewLeaseForm** - Lease renewal
- **NewTenantForm** - Tenant registration
- **TransactionForm** - Transaction management
- **ReportPaymentForm** - Payment reporting

## 🌐 Multi-language Support

The system is designed for easy localization:

1. **Create language-specific configuration files:**
   - `form_labels_en.py` (English)
   - `form_labels_es.py` (Spanish)
   - `form_labels_fr.py` (French)

2. **Import based on current language:**
```python
from django.utils.translation import get_language
if get_language() == 'es':
    from .form_labels_es import FORM_LABELS
else:
    from .form_labels_en import FORM_LABELS
```

## 🔍 Troubleshooting

### Labels Not Appearing
1. Check that the form inherits from the mixin: `BaseCustomModelForm`
2. Verify the form name matches exactly in `FORM_LABELS`
3. Ensure the field name exists in the form

### Form Not Listed in Admin
1. Add the form to `FORM_LABELS` in `form_labels.py`
2. Restart the development server

### Management Command Errors
```bash
# Check if all forms are properly imported
python manage.py shell
>>> from main.form_labels import FORM_LABELS
>>> print(FORM_LABELS.keys())
```

## 📊 Benefits

✅ **Centralized Management** - All labels in one place  
✅ **No Code Changes** - Edit labels without touching form code  
✅ **Consistent UI** - Standardized labeling across the app  
✅ **Easy Localization** - Support for multiple languages  
✅ **Backup & Restore** - Export/import label configurations  
✅ **Developer Friendly** - Simple configuration format  

## 🔄 Making Changes

1. **Edit** `main/form_labels.py`
2. **Save** the file
3. **Refresh** your browser - changes appear immediately!

No server restart required for label changes.

## 📈 Future Enhancements

- [ ] Web-based label editor with real-time preview
- [ ] Automatic form discovery and label generation
- [ ] Translation management integration
- [ ] Label usage analytics
- [ ] Version control for label changes

---

**Need help?** Check the management command: `python manage.py manage_form_labels --help`