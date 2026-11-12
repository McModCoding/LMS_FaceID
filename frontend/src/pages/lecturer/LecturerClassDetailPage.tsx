import { ClassOverview } from '@/components/classes/ClassOverview'
import { GradebookPanel } from '@/components/classes/GradebookPanel'
import { LeaveRequestsPanel } from '@/components/classes/LeaveRequestsPanel'
import { MaterialsPanel } from '@/components/classes/MaterialsPanel'
import { AttendanceReportPanel } from '@/components/attendance/AttendanceReportPanel'
import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { getApiErrorMessage } from '@/lib/api-error'
import { RemoteState } from '@/components/common/RemoteState'
import { ClassPageHeader } from '@/components/classes/ClassPageHeader'

import { Class } from '../../types/class'
import { classesApi } from '../../api/classes'

import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent } from '@/components/ui/tabs'
import { ClassNavigation } from '@/components/classes/ClassNavigation'

import { ClassStudentsTab } from '../../components/classes/ClassStudentsTab'
import { ClassSchedulesTab } from '../../components/classes/ClassSchedulesTab'
import { AttendancePanel } from '../../components/attendance/AttendancePanel'
import { AnnouncementsPanel, AssignmentsPanel, GroupsPanel } from '../../components/classes/LearningTabs'
import { QuestionBankPanel } from '../../components/classes/QuestionBankPanel'
import { ExamDraftPanel } from '../../components/classes/exams/ExamDraftPanel'

export const LecturerClassDetailPage = () => {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const classId = parseInt(id || '0', 10)

  const [classData, setClassData] = useState<Class | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')

  const fetchClassDetail = useCallback(async () => {
    if (!Number.isSafeInteger(classId) || classId <= 0) { setLoadError('Mã lớp học phần không hợp lệ.'); setLoading(false); return }
    setLoading(true); setLoadError(''); setClassData(null)
    try {
      const data = await classesApi.getById(classId)
      setClassData(data)
    } catch (error: unknown) {
      setLoadError(getApiErrorMessage(error, 'Không thể tải thông tin lớp học. Hãy kiểm tra kết nối và thử lại.'))
    } finally {
      setLoading(false)
    }
  }, [classId])

  useEffect(() => {
    fetchClassDetail()
  }, [fetchClassDetail])

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  if (loadError || !classData) {
    return (
      <div className="text-center py-16 space-y-4">
        <RemoteState loading={false} error={loadError || 'Không thể tải thông tin lớp học phần.'} onRetry={fetchClassDetail} />
        <Button variant="outline" onClick={() => navigate('/lecturer/classes')}>
          <ArrowLeft className="mr-2 h-4 w-4" /> Quay lại danh sách lớp
        </Button>
      </div>
    )
  }

  const isClosed = classData.status === 'closed'

  return (
    <div className="space-y-5">

      <ClassPageHeader
        code={classData.code}
        subjectName={classData.subject_name || classData.code}
        semesterName={classData.semester_name}
        lecturerName={classData.lecturer_name}
        status={classData.status}
        backHref="/lecturer/classes"
        backLabel="Lớp giảng dạy"
      />

      <Tabs value={searchParams.get('tab') || 'info'} onValueChange={tab => setSearchParams({ tab }, { replace: true })} className="min-w-0 space-y-4 [&_[role=tabpanel]]:min-w-0">
        <ClassNavigation value={searchParams.get('tab') || 'info'} onChange={tab => setSearchParams({ tab }, { replace: true })} />

        {/* TAB 1: THÔNG TIN CHUNG */}
        <TabsContent value="info"><ClassOverview classData={classData} /></TabsContent>

        {/* TAB 2: SINH VIÊN (Chỉ xem) */}
        <TabsContent value="students">
          <Card>
            <CardContent className="p-5 sm:p-6">
              <ClassStudentsTab
                classData={classData}
                canManage={false}
                onClassUpdated={fetchClassDetail}
              />
            </CardContent>
          </Card>
        </TabsContent>

        {/* TAB 3: LỊCH & BUỔI HỌC */}
        <TabsContent value="schedules">
          <Card>
            <CardContent className="p-5 sm:p-6">
              <ClassSchedulesTab
                classData={classData}
                canManage={!isClosed}
                onClassUpdated={fetchClassDetail}
              />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="attendance">
          <AttendancePanel classId={classData.id} />
        </TabsContent>
        <TabsContent value="assignments"><AssignmentsPanel classId={classData.id} canManage={!isClosed} /></TabsContent>
        <TabsContent value="questions"><QuestionBankPanel subjectId={classData.subject_id} subjectName={classData.subject_name} /></TabsContent>
        <TabsContent value="grades"><GradebookPanel classId={classData.id} writable={!isClosed} /></TabsContent>
        <TabsContent value="exams"><ExamDraftPanel classId={classData.id} subjectId={classData.subject_id} canManage={!isClosed} /></TabsContent>
        <TabsContent value="announcements"><AnnouncementsPanel classId={classData.id} canManage={!isClosed} /></TabsContent>
        <TabsContent value="groups"><GroupsPanel classId={classData.id} canManage={!isClosed} /></TabsContent>
        <TabsContent value="leave"><LeaveRequestsPanel writable={classData.status !== 'closed'} classId={classData.id} /></TabsContent>
        <TabsContent value="report"><AttendanceReportPanel classId={classData.id} /></TabsContent>
        <TabsContent value="materials"><MaterialsPanel classId={classData.id} canManage={!isClosed} /></TabsContent>
      </Tabs>
    </div>
  )
}

export default LecturerClassDetailPage
