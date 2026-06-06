from prisma_browser.models.user import User

_USER = {"id": "x", "externalId": "x", "email": "a@b.c", "name": "n",
         "lastSeen": "2026-01-01T00:00:00Z", "firstSeen": "2026-01-01T00:00:00Z",
         "profilePictureURL": "", "deletedTime": "2026-01-01T00:00:00Z",
         "status": "active", "provider": "local"}


def test_user_round_trip():
    u = User.from_dict(_USER)
    assert u.email == "a@b.c" and u.id == "x"
    d = u.to_dict()
    assert d["email"] == "a@b.c"


def test_user_tolerates_unknown_enum():
    u = User.from_dict({**_USER, "provider": "scm"})
    assert u.provider.value == "scm"
