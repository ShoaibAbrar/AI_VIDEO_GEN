from app.models.user import User, Role


def test_admin_can_list_users(client, db):
    client.post(
        "/api/v1/auth/register",
        json={
            "username": "adminuser",
            "email": "adminuser@example.com",
            "password": "strongpass123",
        },
    )

    admin_user = db.query(User).filter(User.username == "adminuser").one()
    admin_role = db.query(Role).filter(Role.name == "admin").one()
    admin_user.roles.append(admin_role)
    db.commit()

    login = client.post(
        "/api/v1/auth/login",
        json={
            "username": "adminuser",
            "password": "strongpass123",
        },
    )
    token = login.json()["access_token"]

    response = client.get(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert isinstance(payload, list)
    assert any(user["username"] == "adminuser" for user in payload)


def test_non_admin_cannot_manage_users(client):
    client.post(
        "/api/v1/auth/register",
        json={
            "username": "regularuser",
            "email": "regularuser@example.com",
            "password": "strongpass123",
        },
    )

    login = client.post(
        "/api/v1/auth/login",
        json={
            "username": "regularuser",
            "password": "strongpass123",
        },
    )
    token = login.json()["access_token"]

    response = client.get(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403, response.text


def test_admin_can_update_user_roles(client, db):
    client.post(
        "/api/v1/auth/register",
        json={
            "username": "targetuser",
            "email": "targetuser@example.com",
            "password": "strongpass123",
        },
    )

    admin_user = client.post(
        "/api/v1/auth/register",
        json={
            "username": "adminuser2",
            "email": "adminuser2@example.com",
            "password": "strongpass123",
        },
    )
    admin_record = db.query(User).filter(User.username == "adminuser2").one()
    admin_role = db.query(Role).filter(Role.name == "admin").one()
    admin_record.roles.append(admin_role)
    db.commit()

    target_id = db.query(User).filter(User.username == "targetuser").one().id
    login = client.post(
        "/api/v1/auth/login",
        json={
            "username": "adminuser2",
            "password": "strongpass123",
        },
    )
    token = login.json()["access_token"]

    response = client.patch(
        f"/api/v1/admin/users/{target_id}/roles",
        headers={"Authorization": f"Bearer {token}"},
        json={"roles": ["manager"]},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert "manager" in [role["name"] for role in payload["roles"]]
