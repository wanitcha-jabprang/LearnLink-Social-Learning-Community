def normalize_username(username):
    return username.strip()


def normalize_email(email):
    return email.strip()


def validate_full_name(full_name):
    if not full_name:
        raise ValueError("กรุณากรอกชื่อ ชื่อผู้ใช้ อีเมล และรหัสผ่านให้ครบ")
    if len(full_name) > 100:
        raise ValueError("ชื่อต้องมีความยาวไม่เกิน 100 ตัวอักษร")


def validate_follow(actor_id, target_id, *, action):
    if actor_id == target_id:
        raise ValueError(f"ไม่สามารถ{action}ตัวเองได้")
