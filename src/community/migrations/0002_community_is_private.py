from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("community", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="community",
            name="is_private",
            field=models.BooleanField(default=False),
        ),
    ]
