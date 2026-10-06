import { Select } from "./Select";

type Props = {
  value: string; // HH:mm
  onChange: (value: string) => void;
  ariaLabel?: string;
  disabled?: boolean;
  stepMinutes?: 30 | 60;
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

export function TimeField({
  value,
  onChange,
  ariaLabel = "Hora",
  disabled,
  stepMinutes = 30,
}: Props) {
  const options = buildSlots(stepMinutes);
  const safe = options.some((o) => o.value === value) ? value : "09:00";
  return (
    <Select
      value={safe}
      onChange={onChange}
      ariaLabel={ariaLabel}
      disabled={disabled}
      options={options}
    />
  );
}
