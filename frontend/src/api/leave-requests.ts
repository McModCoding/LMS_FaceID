import api from './client'

export type LeaveStatus = 'pending' | 'approved' | 'rejected'
export interface LeaveRequest {
  id: number; session_id: number; class_id: number; session_no: number;
  session_date: string; student_name: string; student_code: string; reason: string;
  status: LeaveStatus; reviewer_name: string | null; reviewed_at: string | null;
  review_note: string | null; created_at: string;
}
export interface LeaveList { items: LeaveRequest[]; total: number; page: number; page_size: number }
export const leaveApi = {
  list: async (student: boolean, params: { class_id: number; status?: LeaveStatus; page: number }) =>
    (await api.get<LeaveList>(student ? '/me/leave-requests' : '/leave-requests', { params })).data,
  create: async (sessionId: number, reason: string) =>
    (await api.post<LeaveRequest>(`/sessions/${sessionId}/leave-requests`, { session_id: sessionId, reason })).data,
  cancel: async (id: number) => (await api.delete(`/leave-requests/${id}`)).data,
  review: async (id: number, decision: 'approve' | 'reject', review_note: string) =>
    (await api.post(`/leave-requests/${id}/review`, { decision, review_note })).data,
}
