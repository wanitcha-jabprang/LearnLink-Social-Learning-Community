from dataclasses import dataclass

from users.application.services import (
    AccountDeletionService,
    UserAccountService,
    UserFollowService,
    UserProfileService,
)
from users.infrastructure.persistence.repositories import (
    AccountDeletionRepository,
    FollowRepository,
    UserProfileRepository,
    UserRepository,
)
from users.infrastructure.storage.files import FileStorage


@dataclass(frozen=True)
class UserServices:
    accounts: UserAccountService
    profiles: UserProfileService
    follows: UserFollowService
    account_deletion: AccountDeletionService


def get_user_services():
    users = UserRepository()
    storage = FileStorage()
    return UserServices(
        accounts=UserAccountService(users),
        profiles=UserProfileService(users, UserProfileRepository(), storage),
        follows=UserFollowService(FollowRepository()),
        account_deletion=AccountDeletionService(
            AccountDeletionRepository(),
            storage,
        ),
    )
