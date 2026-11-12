from common.infrastructure.storage import upload_validation
from community.application.services import CommunityService
from community.infrastructure.persistence.repositories import (
    CommunityRepository,
    MembershipRepository,
)


def get_community_service():
    return CommunityService(
        CommunityRepository(),
        MembershipRepository(),
        upload_validation,
    )
