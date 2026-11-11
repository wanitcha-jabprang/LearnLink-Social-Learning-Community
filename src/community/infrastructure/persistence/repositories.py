from django.contrib.auth import get_user_model

from community.infrastructure.persistence.models import (
    Community,
    CommunityMember,
)


class CommunityRepository:
    def get(self, community_id):
        return Community.objects.filter(pk=community_id).first()

    def create(self, **values):
        return Community.objects.create(**values)

    def save(self, community, fields=None):
        community.save(update_fields=fields)

    def delete(self, community):
        community.delete()

    def find_by_invite_code(self, code):
        return Community.objects.filter(invite_code=code).first()


class MembershipRepository:
    def join(self, community, user):
        return CommunityMember.objects.get_or_create(
            community=community, user=user
        )

    def has_member(self, community, user):
        return CommunityMember.objects.filter(
            community=community, user=user
        ).exists()

    def leave(self, community, user):
        return CommunityMember.objects.filter(
            community=community, user=user
        ).delete()[0]

    def remove(self, community, user):
        return self.leave(community, user)

    def get_user(self, user_id):
        return get_user_model().objects.filter(pk=user_id).first()

    def transfer_candidates(self, community, current_user):
        member_ids = (
            CommunityMember.objects.filter(community=community)
            .exclude(user=current_user)
            .values_list("user_id", flat=True)
        )
        return get_user_model().objects.filter(pk__in=member_ids)
