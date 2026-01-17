from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.models import SocialApp


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Minimal adapter to fix MultipleObjectsReturned error in get_app method.
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
