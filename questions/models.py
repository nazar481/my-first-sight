from django.db import models
from django.contrib.auth.models import User


class Question(models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='questions')
    views_count = models.IntegerField(default=0)
    accepted_answer = models.OneToOneField(
        'Answer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='accepted_for_question'
    )

    def __str__(self):
        return self.title

    # Метод для получения количества лайков
    def likes_count(self):
        return self.likes.count()

    # Метод для проверки, лайкнул ли пользователь вопрос
    def is_liked_by(self, user):
        if not user.is_authenticated:
            return False
        return self.likes.filter(user=user).exists()

    def mark_accepted_answer(self, answer):
        if answer.question_id != self.id:
            raise ValueError("Answer does not belong to this question.")
        self.accepted_answer = answer
        self.save(update_fields=['accepted_answer'])

    @classmethod
    def get_all(cls):
        return cls.objects.all().order_by('-created_at')

    @classmethod
    def create(cls, **kwargs):
        return cls.objects.create(**kwargs)

    objects = models.Manager()


class Answer(models.Model):
    question = models.ForeignKey(Question, related_name='answers', on_delete=models.CASCADE)
    content = models.TextField()
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='answers')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Ответ на: {self.question.title[:50]}"

    @classmethod
    def create(cls, **kwargs):
        return cls.objects.create(**kwargs)

    objects = models.Manager()


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    bio = models.TextField(blank=True)
    location = models.CharField(max_length=100, blank=True)
    website = models.URLField(blank=True)
    def __str__(self):
        return self.user.username
    @classmethod
    def get_or_create(cls, user):
        return cls.objects.get_or_create(user=user)

    @classmethod
    def get_or_create(cls, user):
        try:
            return cls.objects.get(user=user), False
        except cls.DoesNotExist:
            profile = cls.objects.create(user=user)
            return profile, True

    @classmethod
    def create(cls, user):
        return cls.objects.create(user=user)

    objects = models.Manager()


class QuestionLike(models.Model):
    #Модель для лайков (звезд) вопросов
    question = models.ForeignKey(Question, related_name='likes', on_delete=models.CASCADE)
    user = models.ForeignKey(User, related_name='question_likes', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['question', 'user']  # Один пользователь может лайкнуть вопрос только один раз
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} likes {self.question.title}"

