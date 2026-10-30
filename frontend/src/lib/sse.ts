// SSE subscription helper. Connects to the backend event stream for a task run,
// with replay support (?after_seq=) so a reconnect never re-renders old deltas.
import type { SseEvent } from "../types";

export class EventStream {
  private es: EventSource | null = null;
  private closed = false;

  constructor(
    private taskId: string,
    private onEvent: (e: SseEvent) => void,
    private onError?: (err: Event) => void,
    private afterSeq?: number,
  ) {}

  start() {
    let url = `/api/tasks/${this.taskId}/events`;
    if (this.afterSeq != null) url += `?after_seq=${this.afterSeq}`;
    this.es = new EventSource(url);
    this.es.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data) as SseEvent;
        this.onEvent(data);
      } catch { /* ignore malformed frame */ }
    };
    this.es.onerror = (err) => {
      if (this.closed) return;
      this.onError?.(err);
    };
  }

  close() {
    this.closed = true;
    this.es?.close();
    this.es = null;
  }
}
