import { useId } from "react";

/** Choix Oui / Non accessible (boutons radio stylés). */
export function ChoixOuiNon({
  legende,
  valeur,
  onChange,
  aide,
}: {
  legende: string;
  valeur: boolean | null;
  onChange: (v: boolean) => void;
  aide?: string;
}) {
  const nom = useId();
  return (
    <fieldset className="space-y-2">
      <legend className="text-sm font-medium">{legende}</legend>
      <div className="flex gap-2">
        {[true, false].map((option) => (
          <label
            key={String(option)}
            className="flex cursor-pointer items-center gap-2 rounded-md border px-3 py-1.5 text-sm transition-colors has-[:checked]:border-primary has-[:checked]:bg-accent has-[:checked]:text-accent-foreground has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring"
          >
            <input
              type="radio"
              name={nom}
              className="sr-only"
              checked={valeur === option}
              onChange={() => onChange(option)}
              required
            />
            {option ? "Oui" : "Non"}
          </label>
        ))}
      </div>
      {aide && <p className="text-xs text-muted-foreground">{aide}</p>}
    </fieldset>
  );
}
