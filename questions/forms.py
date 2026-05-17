from django import forms
from .models import Question, Answer, Profile
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['bio', 'location', 'website']
        widgets = {
            'bio': forms.Textarea(attrs={'placeholder': 'О себе...', 'rows': 3, 'class': 'form-control'}),
            'location': forms.TextInput(attrs={'placeholder': 'Ваш город', 'class': 'form-control'}),
            'website': forms.URLInput(attrs={'placeholder': 'https://example.com', 'class': 'form-control'}),
        }


class UserRegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']


class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ['title', 'content']


class AnswerForm(forms.ModelForm):
    class Meta:
        model = Answer
        fields = ['content']
        widgets = {
            'content': forms.Textarea(
                attrs={
                    'placeholder': 'Ваш ответ...',
                    'rows': 6,
                }
            ),
        }