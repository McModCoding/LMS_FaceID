import { api } from './client'

export type Assignment = { id: number; class_id: number; title: string; description?: string | null; due_at: string; max_score: number; allow_late: boolean; status: 'draft' | 'published'; has_attachment: boolean; my_submission_id?: number | null; my_submitted_at?: string | null; my_is_late?: boolean | null; my_has_file: boolean; my_score?: number | null; my_feedback?: string | null; availability?: 'submitted' | 'open' | 'late_allowed' | 'closed' | null; pending_count?: number | null; can_submit?: boolean | null }
export type Submission = { id: number; assignment_id: number; student_id: number; student_code?: string | null; student_name?: string | null; text?: string | null; has_file: boolean; submitted_at: string; is_late: boolean; score?: number | null; feedback?: string | null }
export type Announcement = { id: number; class_id?: number | null; author_name: string; title: string; content: string; is_pinned: boolean; created_at: string }
export type Notification = { id: number; type: string; title: string; body: string; link?: string | null; is_read: boolean; created_at: string }
export type Group = { id: number; class_id: number; name: string; members: { student_id: number; student_code: string; full_name: string }[] }
export type AssignmentInput = { title: string; description?: string | null; due_at: string; max_score: number; allow_late: boolean; status: 'draft' | 'published' }

export const learningApi = {
  assignments: (classId: number, page = 1, view = 'all') => api.get<{ items: Assignment[]; total: number }>(`/classes/${classId}/assignments`, { params: { page, page_size: 20, view } }).then(r => r.data),
  createAssignment: (classId: number, payload: AssignmentInput) => api.post<Assignment>(`/classes/${classId}/assignments`, payload).then(r => r.data),
  uploadAssignmentAttachment: (assignmentId: number, file: File) => { const body = new FormData(); body.append('file', file); return api.post<Assignment>(`/assignments/${assignmentId}/attachment`, body, { headers: { 'Content-Type': 'multipart/form-data' } }).then(r => r.data) },
  downloadAssignmentAttachment: (assignmentId: number) => api.get<Blob>(`/assignments/${assignmentId}/attachment`, { responseType: 'blob' }).then(r => r.data),
  submit: (assignmentId: number, text: string) => api.post<Submission>(`/assignments/${assignmentId}/submissions`, { text }).then(r => r.data),
  submitFile: (assignmentId: number, file: File, text?: string) => { const body = new FormData(); body.append('file', file); if (text) body.append('text', text); return api.post<Submission>(`/assignments/${assignmentId}/submissions/file`, body, { headers: { 'Content-Type': 'multipart/form-data' } }).then(r => r.data) },
  downloadSubmission: (submissionId: number) => api.get<Blob>(`/submissions/${submissionId}/file`, { responseType: 'blob' }).then(r => r.data),
  submissions: (assignmentId: number) => api.get<{ items: Submission[] }>(`/assignments/${assignmentId}/submissions`).then(r => r.data),
  grade: (submissionId: number, score: number, feedback?: string) => api.post<Submission>(`/submissions/${submissionId}/grade`, { score, feedback }).then(r => r.data),
  announcements: (classId: number) => api.get<Announcement[]>(`/classes/${classId}/announcements`).then(r => r.data),
  createAnnouncement: (classId: number, payload: Pick<Announcement, 'title' | 'content' | 'is_pinned'>) => api.post<Announcement>(`/classes/${classId}/announcements`, payload).then(r => r.data),
  systemAnnouncements: () => api.get<Announcement[]>('/announcements').then(r => r.data),
  createSystemAnnouncement: (payload: Pick<Announcement, 'title' | 'content' | 'is_pinned'>) => api.post<Announcement>('/announcements', payload).then(r => r.data),
  notifications: () => api.get<{ items: Notification[]; unread_count: number }>('/notifications').then(r => r.data),
  readNotification: (id: number) => api.post(`/notifications/${id}/read`).then(r => r.data),
  readAll: () => api.post('/notifications/read-all').then(r => r.data),
  groups: (classId: number) => api.get<Group[]>(`/classes/${classId}/groups`).then(r => r.data),
  createGroup: (classId: number, name: string) => api.post<Group>(`/classes/${classId}/groups`, { name }).then(r => r.data),
  addMember: (groupId: number, student_id: number) => api.post<Group>(`/groups/${groupId}/members`, { student_id }).then(r => r.data),
  removeMember: (groupId: number, studentId: number) => api.delete<Group>(`/groups/${groupId}/members/${studentId}`).then(r => r.data),
  deleteGroup: (groupId: number) => api.delete(`/groups/${groupId}`),
  randomizeGroups: (classId: number, payload: { group_count?: number; members_per_group?: number; replace_existing?: boolean }) => api.post<Group[]>(`/classes/${classId}/groups/randomize`, payload).then(r => r.data),
}
