// Run: node scripts/test-assignment-time.cjs (uses existing TypeScript/dayjs dependencies).
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const ts = require('typescript')

const source = fs.readFileSync(path.join(__dirname, '../src/lib/assignment-time.ts'), 'utf8')
const code = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, esModuleInterop: true },
}).outputText
const originalTimezone = process.env.TZ
try {
  for (const timezone of ['UTC', 'America/New_York', 'Asia/Ho_Chi_Minh']) {
    process.env.TZ = timezone
    const context = { exports: {}, require }
    vm.runInNewContext(code, context)
    const { assignmentDeadlineToUtc, formatAssignmentDeadline } = context.exports
    assert.equal(assignmentDeadlineToUtc('2026-10-30T17:00'), '2026-10-30T10:00:00.000Z')
    assert.equal(assignmentDeadlineToUtc('2026-10-31T00:30'), '2026-10-30T17:30:00.000Z')
    assert.equal(formatAssignmentDeadline('2026-10-30T10:00:00Z'), '30/10/2026 17:00')
    assert.equal(formatAssignmentDeadline('2026-10-30T17:00:00+07:00'), '30/10/2026 17:00')
    assert.throws(() => assignmentDeadlineToUtc('invalid'))
    console.log(`${timezone}: 5 assertions passed`)
  }
} finally {
  if (originalTimezone === undefined) delete process.env.TZ
  else process.env.TZ = originalTimezone
}
