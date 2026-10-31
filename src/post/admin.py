from django.contrib import admin
from .models import Bookmark, Comment, Like, Post

admin.site.register(Post)
admin.site.register(Comment)
admin.site.register(Like)
admin.site.register(Bookmark)