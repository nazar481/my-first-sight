from django.apps import AppConfig


class QuestionsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'questions'

class YourAppConfig(AppConfig):
    name = 'your_app'

    def ready(self):
        import your_app.signals
