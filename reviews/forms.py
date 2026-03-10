from django import forms
from .models import AppReview

class AppReviewForm(forms.ModelForm):
    class Meta:
        model = AppReview
        fields = ['rating', 'comment']
        widgets = {
            'rating': forms.Select(
                choices=[(i, i) for i in range(1, 6)]
            ),
            'comment': forms.Textarea(attrs={'rows': 3})
        }


from django import forms
from .models import BusReview

class BusReviewForm(forms.ModelForm):
    class Meta:
        model = BusReview
        fields = ["rating", "comment"]
