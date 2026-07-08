/**
 * Minimal async mutex: serializes tasks so they run one at a time in submission
 * order. Used to make all Modbus access (polls and command writes) mutually
 * exclusive on the single, non-reentrant modbus-serial client.
 */
export class Mutex {
  private tail: Promise<unknown> = Promise.resolve();

  run<T>(task: () => Promise<T>): Promise<T> {
    // Chain off the tail regardless of how the previous task settled.
    const result = this.tail.then(task, task);
    this.tail = result.then(
      () => undefined,
      () => undefined,
    );
    return result;
  }
}
