"use client";

import { useEffect, useState, FormEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { RoleGate } from "@/components/RoleGate";
import { Field, TextInput, Select } from "@/components/FormFields";
import { SectionCard, DynamicFieldGrid } from "@/components/DynamicFieldGrid";
import { SubjectCodeInput } from "@/components/SubjectCodeInput";
import { TagFilterInput } from "@/components/TagFilterInput";
import { listFieldDefinitions, listSites, createSample, getSubjectAutofill } from "@/lib/resources";
import { groupFieldsBySections } from "@/lib/fieldSections";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/authContext";
import type { FieldSection } from "@/lib/fieldSections";
import type { Site, SampleType } from "@/lib/types";

const SAMPLE_TYPES: { value: SampleType; label: string }[] = [
  { value: "ffpe", label: "FFPE" },
  { value: "frozen_tumor", label: "Frozen Tumor" },
  { value: "serum", label: "Serum" },
  { value: "plasma", label: "Plasma" },
  { value: "whole_blood", label: "Whole Blood" },
  { value: "other", label: "Other" },
];

function AddSampleContent() {
  const { user } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const presetSiteId = searchParams.get("site_id");

  const [sections, setSections] = useState<FieldSection[]>([]);
  const [sites, setSites] = useState<Site[]>([]);
  const [siteId, setSiteId] = useState(presetSiteId ?? user?.site_id ?? "");
  const [subjectCode, setSubjectCode] = useState("");
  const [sampleCode, setSampleCode] = useState("");
  const [sampleType, setSampleType] = useState<SampleType | "">("");
  const [tags, setTags] = useState<string[]>([]);
  const [customFields, setCustomFields] = useState<Record<string, unknown>>({});
  const [autofilledKeys, setAutofilledKeys] = useState<Set<string>>(new Set());
  const [autofillNotice, setAutofillNotice] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [formFieldError, setFormFieldError] = useState<string | null>(null);

  const isManagerOrAdmin = user?.role === "it_admin" || user?.role === "inventory_manager";

  useEffect(() => {
    listFieldDefinitions().then((defs) => setSections(groupFieldsBySections(defs)));
    if (isManagerOrAdmin) listSites().then(setSites);
  }, [isManagerOrAdmin]);

  async function handleSubjectSelected(code: string) {
    try {
      const res = await getSubjectAutofill(code);
      if (res.found) {
        setCustomFields((prev) => ({ ...prev, ...res.custom_fields }));
        setAutofilledKeys(new Set(Object.keys(res.custom_fields)));
        setAutofillNotice(
          `Pre-filled ${Object.keys(res.custom_fields).length} field(s) from a previous sample for this subject.`
        );
      }
    } catch {
      // Non-critical convenience feature — silently skip on failure.
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setFormError(null);
    setFormFieldError(null);
    try {
      const created = await createSample({
        site_id: siteId,
        subject_id: subjectCode,
        sample_id: sampleCode,
        sample_type: sampleType || undefined,
        tags,
        custom_fields: customFields,
      });
      router.push(`/samples/${created.id}`);
    } catch (err) {
      if (err instanceof ApiError) {
        setFormError(err.message);
        if (err.field === "sample_id") setFormFieldError(err.message);
      } else {
        setFormError("Failed to create sample.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="mb-6 text-2xl font-semibold text-gray-900">Add Sample</h1>

      <form onSubmit={handleSubmit}>
        <SectionCard title="Site & Identifiers">
          {isManagerOrAdmin && (
            <Field label="Site">
              <Select required value={siteId} onChange={(e) => setSiteId(e.target.value)}>
                <option value="">Select a site…</option>
                {sites.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </Select>
            </Field>
          )}

          <Field label="Subject Code">
            <SubjectCodeInput value={subjectCode} onChange={setSubjectCode} onSubjectSelected={handleSubjectSelected} />
          </Field>

          {autofillNotice && (
            <div className="mb-4 flex items-start justify-between rounded-lg bg-amber-50 px-3.5 py-2.5 text-xs text-amber-800">
              <span>{autofillNotice}</span>
              <button type="button" onClick={() => setAutofillNotice(null)} className="ml-3 text-amber-600 hover:text-amber-900">
                Dismiss
              </button>
            </div>
          )}

          <Field label="Sample Code">
            <TextInput
              required
              value={sampleCode}
              onChange={(e) => setSampleCode(e.target.value)}
              className={formFieldError ? "border-red-400" : ""}
            />
            {formFieldError && <p className="mt-1 text-xs text-red-600">{formFieldError}</p>}
          </Field>

          <Field label="Sample Type">
            <Select value={sampleType} onChange={(e) => setSampleType(e.target.value as SampleType)}>
              <option value="">Select…</option>
              {SAMPLE_TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </Select>
          </Field>

          <Field label="Tags">
            <TagFilterInput tags={tags} onChange={setTags} />
          </Field>
        </SectionCard>

        {sections.map((section) => (
          <SectionCard key={section.key} title={section.label} defaultOpen={false}>
            <DynamicFieldGrid
              fields={section.fields}
              values={customFields}
              onChange={(key, value) => setCustomFields((prev) => ({ ...prev, [key]: value }))}
              autofilledKeys={autofilledKeys}
            />
          </SectionCard>
        ))}

        {formError && <div className="mb-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{formError}</div>}

        <button
          type="submit"
          disabled={submitting || !siteId}
          className="w-full rounded-lg bg-brand-gradient px-4 py-3 text-sm font-medium text-white shadow-sm hover:opacity-95 disabled:opacity-60"
        >
          {submitting ? "Saving…" : "Save Sample"}
        </button>
      </form>
    </div>
  );
}

export default function AddSamplePage() {
  return (
    <RoleGate allow={["it_admin", "inventory_manager", "site_user"]}>
      <AddSampleContent />
    </RoleGate>
  );
}
