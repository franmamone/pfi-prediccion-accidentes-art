import { Select } from "./Select";

type Props = {
  value: string; // HH:mm
  onChange: (value: string) => void;
  ariaLabel?: string;
  disabled?: boolean;
  stepMinutes?: 30 | 60;
  /** Si se indica, el combo solo ofrece estas horas (HH:mm). */
  allowedHours?: string[];
};

function buildSlots(step: 30 | 60): { value: string; label: string }[] {
  const out: { value: string; label: string }[] = [];
  for (let h = 7; h <= 20; h++) {
    for (let m = 0; m < 60; m += step) {
      if (h === 20 && m > 0) break;
      const value = `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
      out.push({ value, label: value });
    }
  }
  return out;
}

function normalizeHour(h: string): string {
  return h.slice(0, 5);
}

export function TimeField({
  value,
  onChange,
  ariaLabel = "Hora",
  disabled,
  stepMinutes = 30,
  allowedHours,
}: Props) {
  const options =
    allowedHours && allowedHours.length > 0
      ? allowedHours.map((h) => {
          const v = normalizeHour(h);
          return { value: v, label: v };
        })
      : buildSlots(stepMinutes);
  const safe = options.some((o) => o.value === value) ? value : (options[0]?.value ?? "09:00");
  return (
    <Select
      value={safe}
      onChange={onChange}
      ariaLabel={ariaLabel}
      disabled={disabled || options.length === 0}
      options={options}
    />
  );
}
