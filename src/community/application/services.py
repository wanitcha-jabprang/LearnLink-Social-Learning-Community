from django.db import transaction

from community.domain import policies


class CommunityService:
    def __init__(self, communities, memberships, image_validation):
        self.communities = communities
        self.memberships = memberships
        self.image_validation = image_validation

    @transaction.atomic
    def create(self, *, name, description, image, is_private, owner):
        name = policies.normalize_name(name)
        policies.validate_name(name)
        image_error = self.image_validation.validate_image(image)
        if image_error:
            raise ValueError(image_error)
        community = self.communities.create(
            name=name,
            description=description,
            image=image,
            is_private=is_private,
            invite_code=policies.generate_invite_code(),
            owner=owner,
        )
        self.memberships.join(community, owner)
        return community

    def get(self, community_id):
        community = self.communities.get(community_id)
        if community is None:
            raise LookupError("ไม่พบชุมชนนี้")
        return community

    def update(self, community_id, actor, *, name, description, image, is_private):
        community = self.get(community_id)
        if not policies.is_owner(community.owner_id, actor.pk):
            raise PermissionError("คุณไม่มีสิทธิ์ในการแก้ไขชุมชนนี้")
        image_error = self.image_validation.validate_image(image)
        if image_error:
            raise ValueError(image_error)
        community.name = policies.normalize_name(name)
        policies.validate_name(community.name)
        community.description = description
        community.is_private = is_private
        fields = ["name", "description", "is_private"]
        if image:
            community.image = image
            fields.append("image")
        self.communities.save(community, fields=fields)
        return community

    def join(self, community_id, user, invite_code=""):
        community = self.get(community_id)
        if (
            community.is_private
            and (invite_code or "").strip().upper() != community.invite_code
        ):
            raise ValueError("รหัสเชิญไม่ถูกต้อง")
        self.memberships.join(community, user)
        return community

    def join_by_code(self, code, user):
        community = self.communities.find_by_invite_code(code.strip().upper())
        if community is None:
            raise LookupError("ไม่พบชุมชนจากรหัสเชิญนี้")
        self.memberships.join(community, user)
        return community

    def leave(self, community_id, user):
        community = self.get(community_id)
        if community.owner_id == user.pk:
            raise PermissionError(
                "เจ้าของชุมชนต้องโอนสิทธิ์ความเป็นเจ้าของให้สมาชิกคนอื่นก่อนออกจากชุมชน"
            )
        self.memberships.leave(community, user)
        return community

    def delete(self, community_id, actor):
        community = self.get(community_id)
        if not policies.is_owner(community.owner_id, actor.pk):
            raise PermissionError("คุณไม่มีสิทธิ์ในการลบชุมชนนี้")
        name = community.name
        self.communities.delete(community)
        return name

    @transaction.atomic
    def transfer_ownership(self, community_id, actor, new_owner_id):
        community = self.get(community_id)
        if not policies.is_owner(community.owner_id, actor.pk):
            raise PermissionError("คุณไม่มีสิทธิ์โอนความเป็นเจ้าของชุมชนนี้")
        new_owner = self.memberships.get_user(new_owner_id)
        if new_owner is None:
            raise LookupError("ไม่พบผู้ใช้คนนี้")
        if not self.memberships.has_member(community, new_owner):
            raise ValueError("ไม่สามารถโอนสิทธิ์ได้ ผู้ใช้คนนี้ไม่ได้เป็นสมาชิกในกลุ่ม")
        community.owner = new_owner
        self.communities.save(community, fields=["owner"])
        return community

    def remove_member(self, community_id, actor, member_id):
        community = self.get(community_id)
        if not policies.is_owner(community.owner_id, actor.pk):
            raise PermissionError("คุณไม่มีสิทธิ์ในการลบสมาชิก")
        member = self.memberships.get_user(member_id)
        if member is None:
            raise LookupError("ไม่พบสมาชิกคนนี้ในชุมชน")
        if member.pk == community.owner_id:
            raise ValueError("ไม่สามารถลบเจ้าของชุมชนออกได้")
        if not self.memberships.remove(community, member):
            raise LookupError("ไม่พบสมาชิกคนนี้ในชุมชน")
        return community

    def transfer_candidates(self, community, current_user):
        return self.memberships.transfer_candidates(community, current_user)
