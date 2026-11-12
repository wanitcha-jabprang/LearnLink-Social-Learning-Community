def normalize_content(value, label="โพสต์"):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"กรุณาเขียน{label}ก่อน")
    return value.strip()


def can_access(*, authenticated, community_id, is_owner, is_member):
    if not authenticated:
        return False
    return community_id is None or is_owner or is_member


def is_author(author_id, actor_id):
    return author_id == actor_id
