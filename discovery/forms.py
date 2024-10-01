from django import forms
from .models import Request, RequestResearchers

class RequestForm(forms.ModelForm):
    class Meta:
        model = Request
        fields = ['region', 'importance_score']

class RequestResearchersForm(forms.ModelForm):
    class Meta:
        model = RequestResearchers
        fields = ['explorer', 'quantity', 'is_primary']
