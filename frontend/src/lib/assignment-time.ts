import dayjs from 'dayjs'
import utc from 'dayjs/plugin/utc'
import timezone from 'dayjs/plugin/timezone'

dayjs.extend(utc)
dayjs.extend(timezone)

const TIME_ZONE = 'Asia/Ho_Chi_Minh'

export function assignmentDeadlineToUtc(localValue: string): string {
  return dayjs.tz(localValue, TIME_ZONE).toISOString()
}

export function formatAssignmentDeadline(instant: string): string {
  return dayjs(instant).tz(TIME_ZONE).format('DD/MM/YYYY HH:mm')
}
