def test_create_lecturer_and_duplicate_code(test_client, admin_headers):
    # Tạo giảng viên
    resp = test_client.post(
        "/api/v1/lecturers",
        json={
            "code": "GV999",
            "full_name": "Nguyen Van Thay",
            "email": "gv999@lmstest.edu.vn",
            "phone": "0988888888",
            "department": "Khoa CNTT",
            "type": "full_time",
        },
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert "temp_password" in resp.json()

    # Thử tạo lại với mã GV đã tồn tại -> 400
    resp_dup = test_client.post(
        "/api/v1/lecturers",
        json={
            "code": "GV999",
            "full_name": "Nguyen Van Thay Trung",
            "email": "gv999_dup@lmstest.edu.vn",
            "phone": "0988888889",
            "department": "Khoa CNTT",
            "type": "full_time",
        },
        headers=admin_headers,
    )
    assert resp_dup.status_code == 400
    assert resp_dup.json()["detail"]["code"] == "LECTURER_CODE_EXISTS"
