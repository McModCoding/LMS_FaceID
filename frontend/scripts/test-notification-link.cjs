const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const ts = require('typescript')
const source = fs.readFileSync(path.join(__dirname, '../src/lib/notification-link.ts'), 'utf8')
const exportsObject = {}
vm.runInNewContext(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText, { exports: exportsObject })
const { safeNotificationLink } = exportsObject
test('notification navigation rejects external and ambiguous targets', () => {
  for (const value of ['https://example.com', '//example.com', '/\\example.com', 'javascript:alert(1)', '/\nexample', '/\texample', '', null, undefined]) assert.equal(safeNotificationLink(value), null)
})
test('notification navigation keeps internal routes and query parameters', () => {
  for (const value of ['/student/classes/1?tab=exams', '/lecturer/classes/2?tab=grades', '/admin/dashboard']) assert.equal(safeNotificationLink(value), value)
})
