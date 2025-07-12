import crypto from 'crypto';

export function generateRandomString(length: number): string {
  return crypto.randomBytes(Math.ceil(length / 2)).toString('hex').slice(0, length);
}

export function generateSecureToken(): string {
  return crypto.randomBytes(32).toString('base64url');
}

export function hashString(str: string): string {
  return crypto.createHash('sha256').update(str).digest('hex');
}

export function generateBackupCodes(count: number = 10): string[] {
  const codes: string[] = [];
  for (let i = 0; i < count; i++) {
    codes.push(generateRandomString(8).toUpperCase());
  }
  return codes;
}

export function constantTimeCompare(a: string, b: string): boolean {
  if (a.length !== b.length) {
    return false;
  }
  return crypto.timingSafeEqual(Buffer.from(a), Buffer.from(b));
}