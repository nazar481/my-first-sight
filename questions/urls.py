from django.urls import path
from .views import (
    question_list,
    random_question,
    add_question,
    question_detail,
    register,
    login_view,
    logout_view,
    ProfileView,
    toggle_like,
    set_accepted_answer
)

urlpatterns = [
    path('', question_list, name='question_list'),
    path('random/', random_question, name='random_question'),
    path('add/', add_question, name='add_question'),
    path('question/<int:pk>/', question_detail, name='question_detail'),


    # Auth
    path('register/', register, name='register'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),

    # Profile
    path('profile/<str:username>/', ProfileView.as_view(), name='profile'),
    path('<int:pk>/toggle_like/', toggle_like, name='toggle_like'),
    path('question/<int:question_pk>/accept-answer/<int:answer_pk>/', set_accepted_answer, name='set_accepted_answer'),
]