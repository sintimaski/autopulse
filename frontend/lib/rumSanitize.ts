const EMAIL_PATTERN = /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/gi;
const UUID_PATTERN =
  /\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b/i;
const LONG_HEX_PATTERN = /^[0-9a-f]{16,}$/i;
const TOKENISH_PATTERN = /\b(bearer|token|apikey|api_key|secret|password)=([^&\s]+)/gi;
const DIGITS_PATTERN = /^\d+$/;

function truncate(value: string, maxLength: number): string {
  return value.length <= maxLength ? value : `${value.slice(0, maxLength)}…`;
}

function sanitizeSegment(segment: string): string {
  if (!segment) {
    return segment;
  }
  if (DIGITS_PATTERN.test(segment) || UUID_PATTERN.test(segment) || LONG_HEX_PATTERN.test(segment)) {
    return ":id";
  }
  return segment;
}

export function sanitizeRumText(value: string, maxLength = 160): string {
  const noEmails = value.replace(EMAIL_PATTERN, "[redacted-email]");
  const noTokens = noEmails.replace(TOKENISH_PATTERN, (_match, key: string) => `${key}=[redacted]`);
  return truncate(noTokens, maxLength);
}

export function sanitizeRumPath(pathname: string): string {
  const withoutQuery = pathname.split("?")[0]?.split("#")[0] ?? "/";
  const normalized = withoutQuery.startsWith("/") ? withoutQuery : `/${withoutQuery}`;
  const segments = normalized.split("/").map((segment) => sanitizeSegment(segment));
  return truncate(segments.join("/"), 160);
}

export function sanitizeRumStack(stack: string | undefined | null): string | null {
  if (!stack) {
    return null;
  }
  const firstLines = stack
    .split("\n")
    .slice(0, 2)
    .map((line) => sanitizeRumText(line, 200).replace(/\?.*?(?=\s|$)/g, ""))
    .join("\n")
    .trim();
  return firstLines || null;
}
