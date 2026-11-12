def test_duplicate_subject_code(test_client, admin_headers):
    # Tạo môn học
    test_client.post(
        "/api/v1/subjects",
        json={"code": "TESTIT101", "name": "Nhập môn Lập trình Test", "credits": 3},
        headers=admin_headers,
    )

    # Thử tạo môn học trùng mã
    resp = test_client.post(
        "/api/v1/subjects",
        json={"code": "TESTIT101", "name": "Nhập môn Lập trình Trùng", "credits": 3},
        headers=admin_headers,
    )

    assert resp.status_code == 409
    data = resp.json()
    assert data["detail"]["code"] == "DUPLICATE_CODE"
    assert "TESTIT101" in data["detail"]["message"]
