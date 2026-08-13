def test_create_project_returns_201_with_mock_user(client) -> None:
    response = client.post(
        "/api/projects",
        json={"name": "Demo", "description": "A demo", "repository_path": "/workspace/demo"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Demo"
    assert body["repository_path"] == "/workspace/demo"
    assert body["user_id"] == "00000000-0000-0000-0000-000000000001"


def test_create_project_rejects_empty_name(client) -> None:
    response = client.post("/api/projects", json={"name": "", "repository_path": "/workspace/demo"})
    assert response.status_code == 422


def test_list_projects_returns_created_projects(client) -> None:
    client.post("/api/projects", json={"name": "A", "repository_path": "/workspace/a"})
    client.post("/api/projects", json={"name": "B", "repository_path": "/workspace/b"})

    response = client.get("/api/projects")

    assert response.status_code == 200
    names = {p["name"] for p in response.json()}
    assert names == {"A", "B"}


def test_get_project_returns_404_for_unknown_id(client) -> None:
    response = client.get("/api/projects/00000000-0000-0000-0000-000000000099")
    assert response.status_code == 404


def test_get_project_returns_422_for_malformed_id(client) -> None:
    response = client.get("/api/projects/not-a-uuid")
    assert response.status_code == 422


def test_update_project_patches_only_given_fields(client) -> None:
    create = client.post("/api/projects", json={"name": "A", "repository_path": "/workspace/a"})
    project_id = create.json()["id"]

    response = client.patch(f"/api/projects/{project_id}", json={"description": "updated"})

    assert response.status_code == 200
    body = response.json()
    assert body["description"] == "updated"
    assert body["name"] == "A"


def test_update_project_returns_404_for_unknown_id(client) -> None:
    response = client.patch("/api/projects/00000000-0000-0000-0000-000000000099", json={"name": "X"})
    assert response.status_code == 404


def test_delete_project_removes_it(client) -> None:
    create = client.post("/api/projects", json={"name": "A", "repository_path": "/workspace/a"})
    project_id = create.json()["id"]

    delete_response = client.delete(f"/api/projects/{project_id}")
    assert delete_response.status_code == 204

    get_response = client.get(f"/api/projects/{project_id}")
    assert get_response.status_code == 404


def test_delete_project_returns_404_for_unknown_id(client) -> None:
    response = client.delete("/api/projects/00000000-0000-0000-0000-000000000099")
    assert response.status_code == 404
