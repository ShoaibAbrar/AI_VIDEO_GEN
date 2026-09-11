from app.models.user import User
from app.cli import create_admin_account


def test_logout_revokes_access_token(client):
    client.post(
        "/api/v1/auth/register",
        json={
            "username": "logoutuser",
            "email": "logoutuser@example.com",
            "password": "strongpass123",
        },
    )

    login = client.post(
        "/api/v1/auth/login",
        json={
            "username": "logoutuser",
            "password": "strongpass123",
        },
    )
    token = login.json()["access_token"]

    logout = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert logout.status_code == 200, logout.text

    me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me.status_code == 401, me.text


def test_create_admin_account_function(db):
    user = create_admin_account(db, username="adminseed", email="adminseed@example.com", password="ComplexPass!123")

    assert user.username == "adminseed"
    assert user.has_role("admin")
    assert user.hashed_password != "ComplexPass!123"


def test_admin_can_create_user_and_disable_it(client, db):
    user_payload = {
        "username": "admincreator",
        "email": "admincreator@example.com",
        "password": "strongpass123",
    }
    client.post("/api/v1/auth/register", json=user_payload)

    admin_record = db.query(User).filter(User.username == "admincreator").one()
    admin_role = db.query(User).filter(User.username == "admincreator").first()
    admin_record.roles = []
    db.commit()

    # create a real admin manually via db assignment
    admin_user = db.query(User).filter(User.username == "admincreator").one()
    from app.models.user import Role
    admin_role_row = db.query(Role).filter(Role.name == "admin").first()
    if admin_role_row is not None:
        admin_user.roles.append(admin_role_row)
        db.commit()

    login = client.post(
        "/api/v1/auth/login",
        json={
            "username": "admincreator",
            "password": "strongpass123",
        },
    )
    token = login.json()["access_token"]

    created = client.post(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "username": "manageduser",
            "email": "manageduser@example.com",
            "password": "StrongPass!456",
            "first_name": "Managed",
            "last_name": "User",
        },
    )
    assert created.status_code == 201, created.text

    user_id = created.json()["id"]
    disable = client.patch(
        f"/api/v1/admin/users/{user_id}/status",
        headers={"Authorization": f"Bearer {token}"},
        json={"is_active": False},
    )
    assert disable.status_code == 200, disable.text
    assert disable.json()["is_active"] is False

    enable = client.patch(
        f"/api/v1/admin/users/{user_id}/status",
        headers={"Authorization": f"Bearer {token}"},
        json={"is_active": True},
    )
    assert enable.status_code == 200, enable.text
    assert enable.json()["is_active"] is True
