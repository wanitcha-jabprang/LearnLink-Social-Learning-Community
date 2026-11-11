import uuid


MAX_NAME_LENGTH = 100


def normalize_name(name):
    return name.strip()


def validate_name(name):
    if not name or len(name) > MAX_NAME_LENGTH:
        raise ValueError("กรุณากรอกชื่อชุมชนไม่เกิน 100 ตัวอักษร")


def generate_invite_code():
    return str(uuid.uuid4())[:8].upper()


def is_owner(owner_id, actor_id):
    return owner_id == actor_id
