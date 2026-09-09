/** Format a one-based position as the two-digit catalogue ordinal («01»). */
export function ordinal(position: number): string {
  return String(position).padStart(2, "0");
}
