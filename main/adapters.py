from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.models import SocialApp
from django.contrib.auth import get_user_model


User = get_user_model()


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Custom adapter to fix MultipleObjectsReturned error and auto-login users.
    """
    
    def get_app(self, request, provider, client_id=None):
        """
        Override to gracefully handle multiple SocialApp objects.
        """
        try:
            # If client_id is provided, use it for unique lookup
            if client_id:
                return SocialApp.objects.get(client_id=client_id)
            # Otherwise get the first one for this provider
            app = SocialApp.objects.filter(provider=provider).first()
            if app:
                return app
        except SocialApp.DoesNotExist:
            pass
        except SocialApp.MultipleObjectsReturned:
            # If multiple exist, return the first one
            return SocialApp.objects.filter(provider=provider).first()
        
        # Fall back to parent implementation
        return super().get_app(request, provider, client_id=client_id)
    
    def pre_social_login(self, request, sociallogin):
        """
        Auto-connect user if email matches.
        """
        if sociallogin.is_existing:
            return
        
        try:
            user = User.objects.get(email=sociallogin.account.extra_data.get('email'))
            sociallogin.connect(request, user)
        except User.DoesNotExist:
            pass

    def save_user(self, request, sociallogin, form=None):
        """
        Mark role_confirmed=False for all social login registrations
        so the role selection modal is shown on first dashboard visit.
        """
        user = super().save_user(request, sociallogin, form)
        user.role_confirmed = False
        user.save(update_fields=['role_confirmed'])
        return user