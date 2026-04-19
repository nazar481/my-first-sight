from django.contrib.admin.templatetags.admin_list import paginator_number
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate, logout
from django.template.context_processors import request
from django.utils.functional import empty
from django.views import View
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q, Count, Case, When, Value, IntegerField
from django.utils import timezone
from datetime import timedelta



from .models import Question, Answer, Profile, QuestionLike
from .forms import QuestionForm, AnswerForm, UserRegisterForm


def question_list(request):
    # Базовый queryset
    questions = Question.objects.annotate(likes_count=Count('likes'))

    # --- Фильтры (как у вас были) ---
    q = request.GET.get('q')
    if q:
        questions = questions.filter(Q(title__icontains=q) | Q(content__icontains=q))

    author_id = request.GET.get('author')
    if author_id:
        questions = questions.filter(author_id=author_id)

    period = request.GET.get('period')
    today = timezone.now().date()
    if period == 'today':
        questions = questions.filter(created_at__date=today)
    elif period == 'week':
        week_ago = timezone.now() - timedelta(days=7)
        questions = questions.filter(created_at__gte=week_ago)
    elif period == 'month':
        month_ago = timezone.now() - timedelta(days=30)
        questions = questions.filter(created_at__gte=month_ago)

    has_answers = request.GET.get('has_answers')
    if has_answers == 'yes':
        questions = questions.filter(answers__isnull=False).distinct()
    elif has_answers == 'no':
        questions = questions.filter(answers__isnull=True)

    # Сортировка
    sort = request.GET.get('sort', '-created_at')
    allowed_sort_fields = ['created_at', '-created_at', 'likes_count', '-likes_count', 'views_count', '-views_count']
    if sort in allowed_sort_fields:
        questions = questions.order_by(sort)
    else:
        questions = questions.order_by('-created_at')
    # --- Конец фильтров ---

    # Пагинация (10 вопросов на страницу)
    paginator = Paginator(questions, 10)
    page_number = request.GET.get('page', 1)
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    # Добавляем флаг user_liked для вопросов на текущей странице
    for question in page_obj.object_list:
        question.user_liked = question.is_liked_by(request.user) if request.user.is_authenticated else False

    # Список пользователей для фильтра
    users = User.objects.all()

    context = {
        'page_obj': page_obj,                # основной объект пагинации
        'questions': page_obj.object_list,   # если в шаблоне используется переменная questions
        'users': users,
    }
    return render(request, 'questions/question_list.html', context)



@login_required
def add_question(request):
    if request.method == 'POST':
        form = QuestionForm(request.POST)
        if form.is_valid():
            question = form.save(commit=False)
            question.author = request.user
            question.save()
            messages.success(request, 'Вопрос успешно добавлен!')
            return redirect('question_detail', pk=question.pk)
    else:
        form = QuestionForm()
    return render(request, 'questions/add_question.html', {'form': form})


def question_detail(request, pk):
    question = get_object_or_404(Question, pk=pk)
    answers = question.answers.annotate(
        accepted_order=Case(
            When(pk=question.accepted_answer_id, then=Value(0)),
            default=Value(1),
            output_field=IntegerField()
        )
    ).order_by('accepted_order', '-created_at')

    # Проверяем, лайкнул ли текущий пользователь этот вопрос
    user_liked = question.is_liked_by(request.user) if request.user.is_authenticated else False

    # Увеличиваем счетчик просмотров
    question.views_count += 1
    question.save()

    if request.method == 'POST' and request.user.is_authenticated:
        form = AnswerForm(request.POST)
        if form.is_valid():
            answer = form.save(commit=False)
            answer.question = question
            answer.author = request.user
            answer.save()
            messages.success(request, 'Ответ успешно добавлен!')
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
        messages.info(request, 'Вы сняли отметку лучшего ответа.')
    else:
        question.mark_accepted_answer(answer)
        messages.success(request, 'Лучший ответ выбран.')

    return redirect('question_detail', pk=question_pk)


@login_required
def toggle_like(request, pk):
    #Обработка лайков/дизлайков
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        question = get_object_or_404(Question, pk=pk)
        user = request.user

        # Проверяем, лайкнул ли уже пользователь
        like_exists = QuestionLike.objects.filter(question=question, user=user).exists()

        if like_exists:
            # Убираем лайк
            QuestionLike.objects.filter(question=question, user=user).delete()
            liked = False
            messages.success(request, 'Вы убрали звезду с вопроса')
        else:
            # Добавляем лайк
            QuestionLike.objects.create(question=question, user=user)
            liked = True
            messages.success(request, 'Вы поставили звезду вопросу')

        # Получаем обновленное количество лайков
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
            Profile.create(user=user)
            login(request, user)
            messages.success(request, 'Регистрация успешна!')
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
            messages.success(request, 'Вы успешно вошли в систему!')
            return redirect('question_list')
        else:
            messages.error(request, 'Неверное имя пользователя или пароль')
    return render(request, 'accounts/login.html')


@login_required
def logout_view(request):
    logout(request)
    messages.info(request, 'Вы вышли из системы')
    return redirect('login')


class ProfileView(View):
    def get(self, request, username):
        user = get_object_or_404(User, username=username)
        profile, created = Profile.get_or_create(user)

        # Получаем вопросы с аннотациями (один запрос вместо N+1)
        questions = user.questions.annotate(
            likes_count=Count('likes'),
            answers_count=Count('answers')
        ).order_by('-created_at')

        # Ответы (можно тоже оптимизировать, если нужно)
        answers = user.answers.select_related('question').order_by('-created_at')

        # Общее количество звёзд
        total_stars = sum(q.likes_count for q in questions)

        context = {
            'profile_user': user,
            'profile': profile,
            'questions': questions,
            'answers': answers,
            'questions_count': questions.count(),
            'answers_count': answers.count(),
            'total_stars': total_stars,
        }
        return render(request, 'questions/profile.html', context)