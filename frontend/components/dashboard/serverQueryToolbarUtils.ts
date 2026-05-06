export function isoToLocalInputValue(iso: string): string {
  const date = new Date(iso);
  if (!Number.isFinite(date.getTime())) {
    return "";
  }
  const pad = (n: number) => String(n).padStart(2, "0");
  const yyyy = date.getFullYear();
  const mm = pad(date.getMonth() + 1);
  const dd = pad(date.getDate());
  const hh = pad(date.getHours());
  const min = pad(date.getMinutes());
  return `${yyyy}-${mm}-${dd}T${hh}:${min}`;
}

export function parseLocalDateTimeInput(value: string): Date | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/.exec(value);
  if (!match) {
    return null;
  }
  const [, y, mo, d, h, mi] = match;
  const year = Number(y);
  const monthIndex = Number(mo) - 1;
  const day = Number(d);
  const hour = Number(h);
  const minute = Number(mi);
  const date = new Date(year, monthIndex, day, hour, minute, 0, 0);
  if (!Number.isFinite(date.getTime())) {
    return null;
  }
  return date;
}

export function formatRelativeToUserTime(serverIso: string): string {
  const serverMs = new Date(serverIso).getTime();
  const userMs = Date.now();
  if (!Number.isFinite(serverMs)) {
    return "";
  }
  const diffMinutes = Math.round((serverMs - userMs) / (60 * 1000));
  if (diffMinutes === 0) {
    return "same as your local time";
  }
  if (diffMinutes > 0) {
    return `${diffMinutes}m ahead of your local time`;
  }
  return `${Math.abs(diffMinutes)}m behind your local time`;
}

export function formatWindowMinutes(minutes: number): string {
  if (minutes % 1440 === 0) {
    const days = minutes / 1440;
    return days === 1 ? "1 day" : `${days} days`;
  }
  if (minutes % 60 === 0) {
    const hours = minutes / 60;
    return hours === 1 ? "1 hour" : `${hours} hours`;
  }
  return `${minutes} minutes`;
}
