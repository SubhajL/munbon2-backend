import { createLogger } from '../logger';

const logger = createLogger('retry-utility');

export interface RetryOptions {
  maxAttempts?: number;
  delay?: number;
  backoffMultiplier?: number;
  maxDelay?: number;
  shouldRetry?: (error: Error) => boolean;
  onRetry?: (error: Error, attempt: number) => void;
}

export async function retry<T>(
  fn: () => Promise<T>,
  options: RetryOptions = {}
): Promise<T> {
  const {
    maxAttempts = 3,
    delay = 1000,
    backoffMultiplier = 2,
    maxDelay = 30000,
    shouldRetry = () => true,
    onRetry = (error, attempt) => {
      logger.warn(`Retry attempt ${attempt}`, { error: error.message });
    }
  } = options;

  let lastError: Error;
  let currentDelay = delay;

  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error as Error;

      if (attempt === maxAttempts || !shouldRetry(lastError)) {
        throw lastError;
      }

      onRetry(lastError, attempt);

      // Wait before retrying
      await new Promise(resolve => setTimeout(resolve, currentDelay));

      // Calculate next delay with exponential backoff
      currentDelay = Math.min(currentDelay * backoffMultiplier, maxDelay);
    }
  }

  throw lastError!;
}