from django.db import migrations, models


def copy_old_community_id(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    Post = apps.get_model("post", "Post")
    for post in Post.objects.using(db_alias).all():
        if post.community_id is not None:
            post.old_community_id = post.community_id
            post.save(using=db_alias, update_fields=["old_community_id"])


class Migration(migrations.Migration):

    dependencies = [
        ("post", "0003_post_is_hidden"),
        ("community", "0004_community_image"),
    ]

    operations = [
        migrations.AddField(
            model_name="post",
            name="old_community_id",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="post",
            name="community_uuid_new",
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.RunPython(copy_old_community_id, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="post",
            name="community",
        ),
    ]
