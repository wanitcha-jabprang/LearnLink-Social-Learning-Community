from users.application.services import UserService
from users.infrastructure.persistence.repositories import (
    AccountDeletionRepository,
    FollowRepository,
    UserProfileRepository,
    UserRepository,
)
from users.infrastructure.storage import files


def get_user_service():
    return UserService(
        UserRepository(),
        FollowRepository(),
        UserProfileRepository(),
        AccountDeletionRepository(),
        files,
    )
