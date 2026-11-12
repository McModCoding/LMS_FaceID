"""Compatibility facade for the M5 learning services.

The router imports this module as one stable public contract. Implementation is
split by domain so assignments, announcements/notifications, and groups can be
tested and evolved independently.
"""

from app.services.assignment_service import (
    assignment_attachment_path,
    create_assignment,
    delete_assignment,
    grade_submission,
    list_assignments,
    list_submissions,
    submission_file_path,
    submit_file,
    submit_text,
    update_assignment,
    upload_assignment_attachment,
)
from app.services.assignment_service import (
    assignment_out as _assignment_out,
)
from app.services.assignment_service import (
    submission_out as _submission_out,
)
from app.services.group_service import (
    add_group_member,
    create_group,
    delete_group,
    list_groups,
    randomize_groups,
    remove_group_member,
)
from app.services.notification_service import (
    create_announcement,
    create_system_announcement,
    list_announcements,
    list_notifications,
    list_system_announcements,
    read_all_notifications,
    read_notification,
)

__all__ = [
    "_assignment_out",
    "_submission_out",
    "add_group_member",
    "assignment_attachment_path",
    "create_announcement",
    "create_assignment",
    "create_group",
    "create_system_announcement",
    "delete_assignment",
    "delete_group",
    "grade_submission",
    "list_announcements",
    "list_assignments",
    "list_groups",
    "list_notifications",
    "list_submissions",
    "list_system_announcements",
    "randomize_groups",
    "read_all_notifications",
    "read_notification",
    "remove_group_member",
    "submission_file_path",
    "submit_file",
    "submit_text",
    "update_assignment",
    "upload_assignment_attachment",
]
