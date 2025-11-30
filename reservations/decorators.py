from django.shortcuts import redirect
from django.http import HttpResponse 

def unauthenticated_user(view_func):
    def wrapper_func(request, *args, **kwargs):
        
        email = request.session.get("email")
        if email:
            return view_func(request, *args, **kwargs)
        else:
            return redirect("login")
            
    return wrapper_func
    
def cognito_email_allowed(allowed_emails=None):
    if allowed_emails is None:
        allowed_emails = []

    def decorator(view_func):
        def wrapper_func(request, *args, **kwargs):

            email = request.session.get("email")

            if not email:
                return HttpResponse("Not authorized: Cognito login required")

            if email in allowed_emails:
                return view_func(request, *args, **kwargs)

            return HttpResponse("You are not authorized to view this page")

        return wrapper_func
    return decorator
