import uuid


def generate_auth_code():
    return str(uuid.uuid4())
