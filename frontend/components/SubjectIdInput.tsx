"use client";

import { useEffect, useRef, useState } from "react";
import { getSubjectSuggestions } from "@/lib/resources";
import { TextInput } from "./FormFields";

export function SubjectIdInput({
  value,
  onChange,
  onSubjectSelected,
}: {
  value: string;
  onChange: (value: string) => void;
  /** Fired when the user picks a suggestion or blurs with a full match — triggers the autofill lookup. */
  onSubjectSelected: (subjectId: string) => void;
}) {
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [open, setOpen] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (value.trim().length < 2) {
      setSuggestions([]);
      return;
    }
    debounceRef.current = setTimeout(async () => {
      try {
        const res = await getSubjectSuggestions(value.trim());
        setSuggestions(res.suggestions);
        setOpen(res.suggestions.length > 0);
      } catch {
        // Suggestions are a convenience feature — a failed lookup should
        // never block the user from typing a new subject code manually.
        setSuggestions([]);
      }
    }, 250);
  }, [value]);

  return (
    <div className="relative">
      <TextInput
        required
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onFocus={() => suggestions.length > 0 && setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        placeholder="e.g. GB-01"
      />
      {open && (
        <ul className="absolute z-10 mt-1 w-full rounded-lg border border-gray-200 bg-white py-1 shadow-lg">
          {suggestions.map((s) => (
            <li key={s}>
              <button
                type="button"
                onMouseDown={() => {
                  onChange(s);
                  onSubjectSelected(s);
                  setOpen(false);
                }}
                className="block w-full px-3.5 py-2 text-left text-sm hover:bg-peach-50"
              >
                {s}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
