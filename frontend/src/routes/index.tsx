import { PageLoadBoundary } from '@/components/common/PageLoadBoundary'
import { RemoteState } from '@/components/common/RemoteState'
import React, { lazy, Suspense } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import PrivateRoute from '../auth/PrivateRoute'
import AdminLayout from '../layouts/AdminLayout'
import LecturerLayout from '../layouts/LecturerLayout'
import StudentLayout from '../layouts/StudentLayout'
import { useAuth } from '../auth/AuthContext'
const NotificationsPage = lazy(() => import('../pages/NotificationsPage'))
const SystemInfoPage = lazy(() => import('../pages/admin/SystemInfoPage'))
const WorkDashboardPage = lazy(() => import('../pages/WorkDashboardPage'))
const LoginPage = lazy(() => import('../pages/LoginPage'))
const ForceChangePasswordPage = lazy(() => import('../pages/ForceChangePasswordPage'))

// Layouts

// Admin Pages
const SemestersPage = lazy(() => import('../pages/admin/SemestersPage'))
const SubjectsPage = lazy(() => import('../pages/admin/SubjectsPage'))
const LecturersPage = lazy(() => import('../pages/admin/LecturersPage'))
const StudentsPage = lazy(() => import('../pages/admin/StudentsPage'))
const AuditLogsPage = lazy(() => import('../pages/admin/AuditLogsPage'))
const ClassesPage = lazy(() => import('../pages/admin/classes/ClassesPage'))
const ClassDetailPage = lazy(() => import('../pages/admin/classes/ClassDetailPage'))
const AdminTimetablePage = lazy(() => import('../pages/admin/AdminTimetablePage'))
const DepartmentsPage = lazy(() => import('../pages/admin/DepartmentsPage'))
const DepartmentDetailPage = lazy(() => import('../pages/admin/DepartmentDetailPage'))
const AdminStudentProfilePage = lazy(() => import('../pages/admin/StudentProfilePage'))
const AdminLecturerProfilePage = lazy(() => import('../pages/admin/LecturerProfilePage'))
const FaceSettingsPage = lazy(() => import('../pages/admin/FaceSettingsPage'))
const SystemAnnouncementsPage = lazy(() => import('../pages/admin/SystemAnnouncementsPage'))

// Lecturer Pages
const LecturerClassesPage = lazy(() => import('../pages/lecturer/LecturerClassesPage'))
const LecturerClassDetailPage = lazy(() => import('../pages/lecturer/LecturerClassDetailPage'))
const LecturerTimetablePage = lazy(() => import('../pages/lecturer/LecturerTimetablePage'))
const LecturerSelfProfilePage = lazy(() => import('../pages/lecturer/LecturerProfilePage'))

// Student Pages
const StudentClassesPage = lazy(() => import('../pages/student/StudentClassesPage'))
const StudentClassDetailPage = lazy(() => import('../pages/student/StudentClassDetailPage'))
const StudentTimetablePage = lazy(() => import('../pages/student/StudentTimetablePage'))
const StudentSelfProfilePage = lazy(() => import('../pages/student/StudentProfilePage'))
const FaceEnrollmentPage = lazy(() => import('../pages/student/FaceEnrollmentPage'))
const StudentExamTakingPage = lazy(() => import('../pages/student/StudentExamTakingPage'))
const LiveAttendancePage = lazy(() => import('../pages/lecturer/LiveAttendancePage'))
const LearningMaterialsPage = lazy(() => import('../pages/common/LearningMaterialsPage'))

// Smart redirect sau khi login theo role
const HomeRedirect: React.FC = () => {
  const { user, isAuthenticated, isLoading } = useAuth()
  if (isLoading) return null
  if (!isAuthenticated || !user) return <Navigate to="/login" replace />
  if (user.role === 'admin') return <Navigate to="/admin/dashboard" replace />
  if (user.role === 'lecturer') return <Navigate to="/lecturer/dashboard" replace />
  if (user.role === 'student') return <Navigate to="/student/dashboard" replace />
  return <Navigate to="/login" replace />
}

export const AppRoutes: React.FC = () => {
  return (
    <PageLoadBoundary><Suspense fallback={<div className="p-6"><RemoteState loading /></div>}><Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route
        path="/change-password"
        element={
          <PrivateRoute>
            <ForceChangePasswordPage />
          </PrivateRoute>
        }
      />

      <Route
        path="/admin"
        element={
          <PrivateRoute allowedRoles={['admin']}>
            <AdminLayout />
          </PrivateRoute>
        }
      >
        <Route index element={<Navigate to="/admin/dashboard" replace />} />
        <Route path="notifications" element={<NotificationsPage />} />
        <Route path="dashboard" element={<WorkDashboardPage />} />
        <Route path="classes" element={<ClassesPage />} />
        <Route path="classes/:id" element={<ClassDetailPage />} />
        <Route path="timetable" element={<AdminTimetablePage />} />
        <Route path="semesters" element={<SemestersPage />} />
        <Route path="departments" element={<DepartmentsPage />} />
        <Route path="departments/:id" element={<DepartmentDetailPage />} />
        <Route path="subjects" element={<SubjectsPage />} />
        <Route path="lecturers" element={<LecturersPage />} />
        <Route path="lecturers/:id" element={<AdminLecturerProfilePage />} />
        <Route path="students" element={<StudentsPage />} />
        <Route path="students/:id" element={<AdminStudentProfilePage />} />
        <Route path="announcements" element={<SystemAnnouncementsPage />} />
        <Route path="face" element={<FaceSettingsPage />} />
        <Route path="system-info" element={<SystemInfoPage />} />
        <Route path="audit-logs" element={<AuditLogsPage />} />
      </Route>

      <Route
        path="/lecturer"
        element={
          <PrivateRoute allowedRoles={['lecturer']}>
            <LecturerLayout />
          </PrivateRoute>
        }
      >
        <Route index element={<Navigate to="/lecturer/dashboard" replace />} />
        <Route path="notifications" element={<NotificationsPage />} />
        <Route path="dashboard" element={<WorkDashboardPage />} />
        <Route path="classes" element={<LecturerClassesPage />} />
        <Route path="classes/:id" element={<LecturerClassDetailPage />} />
        <Route path="timetable" element={<LecturerTimetablePage />} />
        <Route path="materials" element={<LearningMaterialsPage role="lecturer" defaultTab="materials" />} />
        <Route path="documents" element={<LearningMaterialsPage role="lecturer" defaultTab="documents" />} />
        <Route path="profile" element={<LecturerSelfProfilePage />} />
        <Route path="sessions/:id/live" element={<LiveAttendancePage />} />
      </Route>

      <Route
        path="/student"
        element={
          <PrivateRoute allowedRoles={['student']}>
            <StudentLayout />
          </PrivateRoute>
        }
      >
        <Route index element={<Navigate to="/student/dashboard" replace />} />
        <Route path="notifications" element={<NotificationsPage />} />
        <Route path="dashboard" element={<WorkDashboardPage />} />
        <Route path="classes" element={<StudentClassesPage />} />
        <Route path="classes/:id" element={<StudentClassDetailPage />} />
        <Route path="exams/:attemptId" element={<StudentExamTakingPage />} />
        <Route path="materials" element={<LearningMaterialsPage role="student" defaultTab="materials" />} />
        <Route path="documents" element={<LearningMaterialsPage role="student" defaultTab="documents" />} />
        <Route path="timetable" element={<StudentTimetablePage />} />
        <Route path="profile" element={<StudentSelfProfilePage />} />
        <Route path="face" element={<FaceEnrollmentPage />} />
      </Route>

      <Route path="/" element={<HomeRedirect />} />
      <Route path="*" element={<HomeRedirect />} />
    </Routes></Suspense></PageLoadBoundary>
  )
}

export default AppRoutes
