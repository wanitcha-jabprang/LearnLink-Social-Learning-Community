from django.contrib import admin
from post.infrastructure.persistence.models import Bookmark, Comment, Like, Post

admin.site.register(Post)
admin.site.register(Comment)
admin.site.register(Like)
admin.site.register(Bookmark)