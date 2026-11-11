from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction

from users.domain import policies


class UserAccountService:
    def __init__(self, users):
        self.users = users

    def login_username(self, identifier):
        identifier = identifier.strip()
        if "@" not in identifier:
            return identifier
        user = self.users.find_by_email(identifier)
        return user.username if user else ""

    def register(self, *, full_name, username, email, password):
        full_name = full_name.strip()
        username = policies.normalize_username(username)
        email = policies.normalize_email(email)
        if not full_name or not username or not email or not password:
            raise ValueError("กรุณากรอกชื่อ ชื่อผู้ใช้ อีเมล และรหัสผ่านให้ครบ")
        try:
            username = self.users.clean_username(username)
        except ValidationError as error:
            raise ValueError("\n".join(error.messages)) from error
        if self.users.username_exists(username):
            raise ValueError("ชื่อผู้ใช้นี้ถูกใช้แล้ว")
        try:
            validate_email(email)
        except ValidationError as error:
            raise ValueError("กรุณากรอกอีเมลให้ถูกต้อง") from error
        policies.validate_full_name(full_name)
        if self.users.email_exists(email):
            raise ValueError("อีเมลนี้ถูกใช้แล้ว")
        try:
            self.users.validate_password(username, full_name, email, password)
        except ValidationError as error:
            raise ValueError("\n".join(error.messages)) from error
        return self.users.create(
            username=username,
            full_name=full_name,
            email=email,
            password=password,
        )

    def get_user(self, user_id):
        return self.users.get(user_id)

    def username_exists_for_other_user(self, username, user_id):
        return self.users.username_exists_for_other_user(username, user_id)


class UserProfileService:
    def __init__(self, users, profiles, file_storage):
        self.users = users
        self.profiles = profiles
        self.file_storage = file_storage

    def save(self, user, fields):
        self.users.save(user, fields)

    def visible_posts(self, profile_user, viewer):
        return self.profiles.visible_posts(profile_user, viewer)

    def counts(self, profile_user, posts):
        return self.profiles.profile_counts(profile_user, posts)

    def update_cover(self, user, image):
        previous = user.profile_cover
        user.profile_cover = image
        self.users.save(user, ["profile_cover"])
        if previous and previous.name != user.profile_cover.name:
            self.file_storage.delete([(previous.storage, previous.name)])


class UserFollowService:
    def __init__(self, follows):
        self.follows = follows

    def follow(self, actor, target):
        policies.validate_follow(actor.pk, target.pk, action="ติดตาม")
        _, created = self.follows.add(actor, target)
        return created

    def unfollow(self, actor, target):
        policies.validate_follow(actor.pk, target.pk, action="เลิกติดตาม")
        return bool(self.follows.remove(actor, target))

    def is_following(self, actor, target):
        return self.follows.is_following(actor, target)


class AccountDeletionService:
    def __init__(self, account_deletion, file_storage):
        self.account_deletion = account_deletion
        self.file_storage = file_storage

    @staticmethod
    def password_matches(user, password):
        return user.check_password(password)

    @transaction.atomic
    def delete_account(self, user):
        communities_to_delete = []
        for community in self.account_deletion.owned_communities(user):
            successor = self.account_deletion.successor(community, user)
            if successor:
                self.account_deletion.transfer_owner(community, successor)
            else:
                communities_to_delete.append(community)
        files = self.account_deletion.media_for_deletion(
            user, communities_to_delete
        )
        self.account_deletion.delete_communities(communities_to_delete)
        self.account_deletion.delete_user(user)
        transaction.on_commit(lambda: self.file_storage.delete(files))
