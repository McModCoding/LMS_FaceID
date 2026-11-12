export type AnswerDraft = { selected_option_ids?: number[] | null; essay_text?: string | null }
export type SaveState = 'idle' | 'saving' | 'saved' | 'error'

/** One writer per attempt. Keep each latest draft until that exact revision is acknowledged. */
export class ExamAnswerQueue {
  private pending = new Map<number, AnswerDraft>()
  private active: Promise<void> | null = null
  private timer: ReturnType<typeof setTimeout> | undefined
  private paused = false

  constructor(
    private save: (questionId: number, draft: AnswerDraft) => Promise<unknown>,
    private onState: (state: SaveState) => void,
    private onError: (error: unknown) => void,
    private delay = 600,
  ) {}

  get hasPending() { return this.pending.size > 0 }
  drafts() { return new Map(this.pending) }

  enqueue(questionId: number, draft: AnswerDraft) {
    this.pending.set(questionId, {
      ...draft,
      selected_option_ids: draft.selected_option_ids?.slice() ?? draft.selected_option_ids,
    })
    this.emit('saving')
    this.schedule()
  }

  private emit(state: SaveState) { if (!this.paused) this.onState(state) }
  private cancelTimer() { clearTimeout(this.timer); this.timer = undefined }
  private schedule() {
    this.cancelTimer()
    if (!this.paused) this.timer = setTimeout(() => {
      this.timer = undefined
      void this.flush().catch((error) => { if (!this.paused) this.onError(error) })
    }, this.delay)
  }

  flush(): Promise<void> {
    this.cancelTimer()
    if (this.active) return this.active
    this.active = this.drain().finally(() => { this.active = null })
    return this.active
  }

  private async drain() {
    try {
      while (this.pending.size && !this.paused) {
        const [id, draft] = this.pending.entries().next().value!
        this.emit('saving')
        await this.save(id, draft)
        if (this.pending.get(id) === draft) this.pending.delete(id)
      }
      if (!this.pending.size) { this.cancelTimer(); this.emit('saved') }
    } catch (error) {
      this.cancelTimer()
      this.emit('error')
      throw error
    }
  }

  clear() { this.cancelTimer(); this.pending.clear() }
  pause() { this.paused = true; this.cancelTimer() }
  resume() { this.paused = false; if (this.hasPending) this.schedule() }
}
