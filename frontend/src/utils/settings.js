export function parseSetting(value) {
  const number = Number(value);
  if (!Number.isNaN(number) && value.trim() !== "") return number;
  return value;
}
