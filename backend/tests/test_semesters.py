from app.models.semester import Semester


def test_semester_unique_is_current(test_client, admin_headers, db_session):
    # Tạo học kỳ 1 có is_current = True
    resp1 = test_client.post(
        "/api/v1/semesters",
        json={
            "name": "Học kỳ 1 2026-2027",
            "start_date": "2026-09-01",
            "end_date": "2027-01-15",
            "is_current": True,
        },
        headers=admin_headers,
    )
    assert resp1.status_code == 200
    sem1_id = resp1.json()["id"]

    # Tạo học kỳ 2 có is_current = True -> Học kỳ 1 phải tự động chuyển thành is_current = False
    resp2 = test_client.post(
        "/api/v1/semesters",
        json={
            "name": "Học kỳ 2 2026-2027",
            "start_date": "2027-02-01",
            "end_date": "2027-06-30",
            "is_current": True,
        },
        headers=admin_headers,
    )
    assert resp2.status_code == 200
    sem2_id = resp2.json()["id"]

    # Kiểm tra trong DB: chỉ có duy nhất 1 học kỳ có is_current = True
    db_session.rollback()
    current_semesters = db_session.query(Semester).filter(Semester.is_current == True).all()
    assert len(current_semesters) == 1
    assert current_semesters[0].id == sem2_id

    sem1 = db_session.query(Semester).filter(Semester.id == sem1_id).first()
    assert sem1.is_current is False
