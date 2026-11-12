const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const ts = require('typescript')
const { test } = require('node:test')

const code = ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src/lib/exam-answer-queue.ts'), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS },
}).outputText
const context = { exports: {}, setTimeout, clearTimeout }
vm.runInNewContext(code, context)
const { ExamAnswerQueue } = context.exports
const deferred = () => {
  let resolve, reject
  const promise = new Promise((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}
const tick = () => new Promise((resolve) => setImmediate(resolve))
const create = (save, delay = 60000) => {
  const states = [], errors = []
  const queue = new ExamAnswerQueue(save, (value) => states.push(value), (error) => errors.push(error), delay)
  return { queue, states, errors }
}

test('happy: latest debounced draft is saved, then pending clears', async () => {
  const calls = []
  const { queue, states } = create(async (id, draft) => calls.push([id, draft.essay_text]))
  queue.enqueue(1, { essay_text: 'old' }); queue.enqueue(1, { essay_text: 'new' })
  await queue.flush()
  assert.deepEqual(calls, [[1, 'new']]); assert.equal(queue.hasPending, false)
  assert.equal(states.at(-1), 'saved')
})

test('race: old acknowledgement cannot delete the newer draft or mark it saved', async () => {
  const first = deferred(), second = deferred(), calls = []
  const { queue, states } = create(async (_id, draft) => {
    calls.push(draft.essay_text)
    await (calls.length === 1 ? first.promise : second.promise)
  })
  queue.enqueue(1, { essay_text: 'old' }); const work = queue.flush()
  queue.enqueue(1, { essay_text: 'new' })
  assert.deepEqual(calls, ['old'])
  first.resolve(); await tick()
  assert.deepEqual(calls, ['old', 'new']); assert.equal(queue.hasPending, true)
  assert.notEqual(states.at(-1), 'saved')
  second.resolve(); await work; assert.equal(queue.hasPending, false)
})

test('submit barrier: repeated flush shares in-flight saves; submit waits for latest answer', async () => {
  const first = deferred(), latest = deferred(), events = []
  const { queue } = create(async (_id, draft) => {
    events.push(draft.essay_text); await (draft.essay_text === 'old' ? first.promise : latest.promise)
  })
  queue.enqueue(1, { essay_text: 'old' }); const saving = queue.flush()
  queue.enqueue(1, { essay_text: 'new' })
  assert.equal(queue.flush(), saving)
  const submitting = queue.flush().then(() => events.push('submit'))
  assert.deepEqual(events, ['old'])
  first.resolve(); await tick(); assert.deepEqual(events, ['old', 'new'])
  latest.resolve(); await submitting; assert.deepEqual(events, ['old', 'new', 'submit'])
})

test('network failure: keep latest draft and block submit until a successful retry', async () => {
  const first = deferred(), calls = []
  const { queue, states } = create(async (_id, draft) => {
    calls.push(draft.essay_text); if (calls.length === 1) await first.promise
  })
  queue.enqueue(1, { essay_text: 'old' }); const saving = queue.flush()
  queue.enqueue(1, { essay_text: 'new' })
  let submitted = false
  const blocked = saving.then(() => { submitted = true })
  first.reject(new Error('offline'))
  await assert.rejects(blocked, /offline/)
  assert.equal(submitted, false); assert.equal(queue.hasPending, true)
  assert.equal(queue.drafts().get(1).essay_text, 'new'); assert.equal(states.at(-1), 'error')
  await queue.flush(); assert.deepEqual(calls, ['old', 'new']); assert.equal(queue.hasPending, false)
})

test('multiple questions: failure retains unsent questions, retry does not repeat acknowledged answers', async () => {
  let failing = true
  const calls = []
  const { queue } = create(async (id) => { calls.push(id); if (id === 2 && failing) throw new Error('offline') })
  for (const id of [1, 2, 3]) queue.enqueue(id, { essay_text: String(id) })
  await assert.rejects(queue.flush(), /offline/)
  assert.deepEqual([...queue.drafts().keys()], [2, 3])
  failing = false; await queue.flush(); assert.deepEqual(calls, [1, 2, 2, 3])
})

test('request order: edits during save produce no concurrent writes, intermediate drafts coalesce', async () => {
  const gate = deferred(), calls = []
  let running = 0, maxRunning = 0
  const { queue } = create(async (_id, draft) => {
    running++; maxRunning = Math.max(maxRunning, running); calls.push(draft.essay_text)
    if (calls.length === 1) await gate.promise
    running--
  })
  queue.enqueue(1, { essay_text: 'A' }); const work = queue.flush()
  queue.enqueue(1, { essay_text: 'B' }); queue.enqueue(1, { essay_text: 'C' })
  gate.resolve(); await work
  assert.deepEqual(calls, ['A', 'C']); assert.equal(maxRunning, 1)
})

test('draft payload is copied; caller mutation cannot change queued selections', async () => {
  const values = [1], calls = []
  const { queue } = create(async (_id, draft) => calls.push([...draft.selected_option_ids]))
  queue.enqueue(1, { selected_option_ids: values }); values.push(2)
  await queue.flush(); assert.deepEqual(calls, [[1]])
})

test('automatic debounce failure is visible and leaves data retryable', async () => {
  const error = deferred()
  const queue = new ExamAnswerQueue(async () => { throw new Error('offline') }, () => {}, error.resolve, 0)
  queue.enqueue(1, { essay_text: 'A' })
  assert.match((await error.promise).message, /offline/)
  assert.equal(queue.hasPending, true); queue.pause()
})

test('lifecycle: pause cancels debounce, resume (StrictMode) saves the retained draft', async () => {
  const done = deferred(), calls = []
  const queue = new ExamAnswerQueue(async (id) => { calls.push(id); done.resolve() }, () => {}, () => {}, 0)
  queue.enqueue(1, { essay_text: 'A' }); queue.pause()
  await tick(); assert.deepEqual(calls, []); assert.equal(queue.hasPending, true)
  queue.resume(); await done.promise; await queue.flush()
  assert.deepEqual(calls, [1]); assert.equal(queue.hasPending, false)
})

test('attempt isolation: old queue response cannot clear another attempt draft', async () => {
  const gate = deferred()
  const { queue: old } = create(async () => gate.promise)
  const { queue: next } = create(async () => {})
  old.enqueue(1, { essay_text: 'attempt 1' }); const work = old.flush(); old.pause()
  next.enqueue(1, { essay_text: 'attempt 2' })
  gate.resolve(); await work
  assert.equal(next.drafts().get(1).essay_text, 'attempt 2'); next.pause()
})

test('terminal response: clear drops unsaved drafts only after server closes the attempt', async () => {
  const { queue } = create(async () => {})
  queue.enqueue(1, { essay_text: 'not saved' })
  assert.equal(queue.hasPending, true); queue.clear(); assert.equal(queue.hasPending, false)
  await queue.flush()
})
