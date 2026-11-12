# Trọng số FaceID (không đóng gói)

Thư mục này chứa hai tệp ONNX của OpenCV Zoo mà `FACE_ENGINE=opencv` cần:

- `face_detection_yunet_2023mar.onnx` — phát hiện khuôn mặt (YuNet)
- `face_recognition_sface_2021dec.onnx` — trích xuất vector 128 chiều (SFace)

Tải bằng `python face_tools/download_face_models.py` (cần mạng). Tệp `*.onnx` nằm trong `.gitignore`;
không commit trọng số, ảnh khuôn mặt hay embedding. Kiểm tra giấy phép của từng mô hình ở kho
OpenCV Zoo trước khi phân phối lại. Ghi lại SHA-256 được in ra để báo cáo thực nghiệm lặp lại được.
