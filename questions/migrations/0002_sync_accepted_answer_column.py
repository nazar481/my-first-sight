from django.db import migrations


def add_missing_accepted_answer_column(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("PRAGMA table_info('questions_question')")
        columns = {row[1] for row in cursor.fetchall()}

    if "accepted_answer_id" not in columns:
        schema_editor.execute(
            'ALTER TABLE "questions_question" ADD COLUMN "accepted_answer_id" bigint NULL'
        )


class Migration(migrations.Migration):
    dependencies = [
        ("questions", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            add_missing_accepted_answer_column,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
