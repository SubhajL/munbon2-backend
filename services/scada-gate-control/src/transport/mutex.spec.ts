import { describe, expect, test } from 'vitest';
import { Mutex } from './mutex';

const delay = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

describe('Mutex', () => {
  test('runs tasks one at a time in submission order, never interleaving', async () => {
    const mutex = new Mutex();
    const log: string[] = [];
    const task = (id: string) => async () => {
      log.push(`start:${id}`);
      await delay(1);
      log.push(`end:${id}`);
    };

    await Promise.all([mutex.run(task('a')), mutex.run(task('b')), mutex.run(task('c'))]);

    expect(log).toEqual(['start:a', 'end:a', 'start:b', 'end:b', 'start:c', 'end:c']);
  });

  test('returns each task result to its own caller', async () => {
    const mutex = new Mutex();
    const [a, b] = await Promise.all([mutex.run(async () => 'a'), mutex.run(async () => 'b')]);
    expect([a, b]).toEqual(['a', 'b']);
  });

  test('a rejected task does not block subsequent tasks', async () => {
    const mutex = new Mutex();
    const failed = mutex.run(async () => {
      throw new Error('boom');
    });
    await expect(failed).rejects.toThrow('boom');
    await expect(mutex.run(async () => 'ok')).resolves.toBe('ok');
  });
});
