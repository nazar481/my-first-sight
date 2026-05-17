from datetime import timedelta
import re
import random

from django.contrib import messages
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q, Count, Case, When, Value, IntegerField, F
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views import View

from .forms import QuestionForm, AnswerForm, UserRegisterForm, ProfileForm
from .models import Question, Answer, Profile, QuestionLike


def question_list(request):
    questions = Question.objects.select_related('author', 'author__profile').annotate(
        likes_count=Count('likes', distinct=True),
        answers_count=Count('answers', distinct=True),
    )

    q = request.GET.get('q', '')
    q = q.strip()
    if q:
        normalized_query = q.lower().replace('ё', 'е')
        terms = [term for term in re.split(r'\s+', normalized_query) if term]

        def apply_and_search(qs, words):
            out = qs
            for term in words:
                out = out.filter(
                    Q(title__icontains=term)
                    | Q(content__icontains=term)
                    | Q(author__username__icontains=term)
                    | Q(answers__content__icontains=term)
                )
            return out.distinct()

        def apply_or_search(qs, words):
            combined = Q()
            for term in words:
                combined |= (
                    Q(title__icontains=term)
                    | Q(content__icontains=term)
                    | Q(author__username__icontains=term)
                    | Q(answers__content__icontains=term)
                )
            return qs.filter(combined).distinct()

        strict_qs = apply_and_search(questions, terms)
        if strict_qs.exists():
            questions = strict_qs
        else:
            questions = apply_or_search(questions, terms)

    questions = questions.order_by('-created_at')

    paginator = Paginator(questions, 10)
    page_number = request.GET.get('page', 1)
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    if request.user.is_authenticated:
        question_ids = [question.id for question in page_obj.object_list]
        liked_ids = set(
            QuestionLike.objects.filter(
                user=request.user,
                question_id__in=question_ids
            ).values_list('question_id', flat=True)
        )
        for question in page_obj.object_list:
            question.user_liked = question.id in liked_ids
    else:
        for question in page_obj.object_list:
            question.user_liked = False

    users = User.objects.all()

    query_params = request.GET.copy()
    query_params.pop('page', None)
    for key in list(query_params.keys()):
        if key != 'q':
            query_params.pop(key, None)

    context = {
        'page_obj': page_obj,
        'questions': page_obj.object_list,
        'users': users,
        'querystring': query_params.urlencode(),
        'search_query': q,
    }
    return render(request, 'questions/question_list.html', context)


def random_question(request):
    pks = list(Question.objects.values_list('pk', flat=True))
    if not pks:
        messages.info(request, 'Пока нет ни одного вопроса.')
        return redirect('question_list')
    pk = random.choice(pks)
    return redirect('question_detail', pk=pk)


@login_required
def add_question(request):
    if request.method == 'POST':
        form = QuestionForm(request.POST)
        if form.is_valid():
            question = form.save(commit=False)
            question.author = request.user
            question.save()
            messages.success(request, 'Вопрос успешно добавлен')
            return redirect('question_detail', pk=question.pk)
    else:
        form = QuestionForm()
    return render(request, 'questions/add_question.html', {'form': form})


def question_detail(request, pk):
    question = get_object_or_404(Question.objects.select_related('author', 'author__profile'), pk=pk)
    answers = question.answers.select_related('author', 'author__profile').annotate(
        accepted_order=Case(
            When(pk=question.accepted_answer_id, then=Value(0)),
            default=Value(1),
            output_field=IntegerField()
        )
    ).order_by('accepted_order', '-created_at')

    user_liked = question.is_liked_by(request.user) if request.user.is_authenticated else False

    if request.method == 'GET':
        Question.objects.filter(pk=question.pk).update(views_count=F('views_count') + 1)
        question.refresh_from_db(fields=['views_count'])

    if request.method == 'POST' and request.user.is_authenticated:
        form = AnswerForm(request.POST)
        if form.is_valid():
            answer = form.save(commit=False)
            answer.question = question
            answer.author = request.user
            answer.save()
            messages.success(request, 'Ответ успешно добавлен')
            return redirect('question_detail', pk=pk)
    else:
        form = AnswerForm()

    context = {
        'question': question,
        'answers': answers,
        'form': form,
        'user_liked': user_liked,
        'likes_count': question.likes_count(),
    }
    return render(request, 'questions/question_detail.html', context)


@login_required
def set_accepted_answer(request, question_pk, answer_pk):
    if request.method != 'POST':
        return redirect('question_detail', pk=question_pk)

    question = get_object_or_404(Question, pk=question_pk)
    answer = get_object_or_404(Answer, pk=answer_pk, question=question)

    if request.user != question.author:
        messages.error(request, 'Только автор вопроса может выбрать лучший ответ.')
        return redirect('question_detail', pk=question_pk)

    if question.accepted_answer_id == answer.id:
        question.accepted_answer = None
        question.save(update_fields=['accepted_answer'])
    else:
        question.mark_accepted_answer(answer)

    return redirect('question_detail', pk=question_pk)


@login_required
def set_bad_answer(request, question_pk, answer_pk):
    if request.method != 'POST':
        return redirect('question_detail', pk=question_pk)

    question = get_object_or_404(Question, pk=question_pk)
    answer = get_object_or_404(Answer, pk=answer_pk, question=question)

    if request.user != question.author:
        messages.error(request, 'Только автор вопроса может отметить ответ как плохой.')
        return redirect('question_detail', pk=question_pk)

    answer.is_bad = not answer.is_bad
    answer.save(update_fields=['is_bad'])

    return redirect('question_detail', pk=question_pk)


@login_required
def toggle_like(request, pk):
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        question = get_object_or_404(Question, pk=pk)
        user = request.user

        like_exists = QuestionLike.objects.filter(question=question, user=user).exists()

        if like_exists:
            QuestionLike.objects.filter(question=question, user=user).delete()
            liked = False
        else:
            QuestionLike.objects.create(question=question, user=user)
            liked = True

        likes_count = question.likes_count()

        return JsonResponse({
            'liked': liked,
            'likes_count': likes_count,
            'message': 'Success'
        })

    return JsonResponse({'error': 'Invalid request'}, status=400)


def register(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            Profile.get_or_create(user=user)
            login(request, user)
            messages.success(request, 'Регистрация успешна')
            return redirect('question_list')
    else:
        form = UserRegisterForm()
    return render(request, 'accounts/register.html', {'form': form})


def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, 'Вы успешно вошли в систему')
            return redirect('question_list')
        else:
            messages.error(request, 'Неверное имя пользователя или пароль')
    return render(request, 'accounts/login.html')


@login_required
def logout_view(request):
    list(messages.get_messages(request))
    logout(request)
    messages.info(request, 'Вы вышли из системы')
    return redirect('login')


@login_required
def edit_profile(request):
    profile, created = Profile.get_or_create(request.user)
    profile_score = profile.get_score()
    
    thresholds = [
        (0, 'Начинающий'),
        (1, 'Новичок'),
        (10, 'Знаток'),
        (25, 'Эксперт'),
        (50, 'Гуру помощи'),
        (100, 'Легенда ответов'),
    ]
    earned_titles = [t for thr, t in thresholds if profile_score >= thr]

    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            chosen = request.POST.get('chosen_title', '')
            profile.chosen_title = chosen or None
            profile.save(update_fields=['chosen_title'])
            messages.success(request, 'Профиль успешно обновлён')
            return redirect('profile', username=request.user.username)
    else:
        form = ProfileForm(instance=profile)

    score_title = profile.get_title()

    context = {
        'form': form,
        'profile': profile,
        'earned_titles': earned_titles,
        'selected_title': profile.chosen_title or '',
        'profile_score': profile_score,
        'score_title': score_title,
    }
    return render(request, 'questions/edit_profile.html', context)


class ProfileView(View):
    def get(self, request, username):
        user = get_object_or_404(User, username=username)
        profile, created = Profile.get_or_create(user)

        questions = user.questions.annotate(
            likes_count=Count('likes'),
            answers_count=Count('answers')
        ).order_by('-created_at')

        answers = user.answers.select_related('question').order_by('-created_at')

        answer_count = answers.count()
        accepted_count = answers.filter(question__accepted_answer_id=F('id')).count()
        bad_count = answers.filter(is_bad=True).count()
        profile_score = answer_count + accepted_count * 10 - bad_count * 2
        if profile_score < 0:
            profile_score = 0
        
        score_title = profile.get_title()
        
        score_percent = min(profile_score, 100)
        total_stars = sum(q.likes_count for q in questions)

        context = {
            'profile_user': user,
            'profile': profile,
            'questions': questions,
            'answers': answers,
            'questions_count': questions.count(),
            'answers_count': answer_count,
            'total_stars': total_stars,
            'profile_score': profile_score,
            'score_title': score_title,
            'score_percent': score_percent,
            'accepted_answers_count': accepted_count,
            'bad_answers_count': bad_count,
        }
        return render(request, 'questions/profile.html', context)