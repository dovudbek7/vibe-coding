from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.utils import timezone

from .models import Category, Transaction


class RegistrationForm(UserCreationForm):
    username = None
    name = forms.CharField(max_length=150)
    email = forms.EmailField()

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('name', 'email', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        placeholders = {
            'name': 'Full name',
            'email': 'name@example.com',
            'password1': 'Create a password',
            'password2': 'Confirm your password',
        }
        for name, field in self.fields.items():
            field.widget.attrs.update(
                {
                    'class': 'w-full rounded-2xl border-0 bg-surface-low px-4 py-4 focus:ring-2 focus:ring-primary/20',
                    'placeholder': placeholders.get(name, ''),
                }
            )

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('This email is already registered.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        name = self.cleaned_data['name'].strip()
        user.username = self.cleaned_data['email'].lower()
        user.email = self.cleaned_data['email'].lower()
        user.first_name = name
        if commit:
            user.save()
        return user


class TransactionForm(forms.ModelForm):
    created_at = forms.DateTimeField(
        initial=timezone.now,
        input_formats=['%Y-%m-%dT%H:%M'],
        widget=forms.DateTimeInput(
            format='%Y-%m-%dT%H:%M',
            attrs={'type': 'datetime-local'},
        ),
    )

    class Meta:
        model = Transaction
        fields = ('title', 'amount', 'category', 'type', 'note', 'created_at')

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = Category.objects.filter(user=user)
        self.fields['type'].choices = Transaction.TransactionType.choices
        self.fields['note'].required = False
        for field in self.fields.values():
            field.widget.attrs.update(
                {
                    'class': 'w-full rounded-2xl border-0 bg-surface-low px-4 py-4 focus:ring-2 focus:ring-primary/20',
                }
            )
        self.fields['note'].widget.attrs.update({'rows': 4, 'placeholder': 'Optional note'})
        self.fields['title'].widget.attrs.update({'placeholder': 'What was this for?'})
        self.fields['amount'].widget.attrs.update({'placeholder': '0.00', 'step': '0.01'})

    def clean_amount(self):
        amount = self.cleaned_data['amount']
        if amount <= 0:
            raise forms.ValidationError('Amount must be greater than zero.')
        return amount
