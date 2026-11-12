import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("post", "0004_community_uuid_temp"),
        ("community", "0005_alter_community_id_communitydocument_communityreport"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="post",
            name="old_community_id",
        ),
        migrations.RenameField(
            model_name="post",
            old_name="community_uuid_new",
            new_name="community",
        ),
        migrations.AlterField(
            model_name="post",
            name="community",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to="community.community"),
        ),
    ]
