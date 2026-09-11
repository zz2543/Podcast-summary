import { Plus, SlidersHorizontal } from "lucide-react";
import { useState } from "react";
import {
  Modal,
  ModalBody,
  ModalContent,
  ModalFooter,
  useModalControls
} from "@/components/ui/animated-modal";
import { IridescentButton } from "@/components/ui/iridescent-button";
import { Tabs } from "@/components/ui/tabs";
import { FileUpload } from "@/components/ui/file-upload";
import {
  ApiError,
  createEpisode,
  createEpisodeBatch,
  STYLE_NOTE_MAX_CHARS,
  type CreateEpisodeInput,
  type DetailLevel,
  type SummaryStyleInput,
  type SummaryStylePreset
} from "@/api/client";

export function SubmitModal({ onSubmitted }: { onSubmitted: () => void }) {
  return (
    <Modal>
      <SubmitTrigger />
      <ModalBody>
        <SubmitForm onSubmitted={onSubmitted} />
      </ModalBody>
    </Modal>
  );
}

function SubmitTrigger() {
  const { setOpen } = useModalControls();
  return (
    <IridescentButton onClick={() => setOpen(true)} size="sm">
      <Plus className="mr-1 h-4 w-4" strokeWidth={2.4} />
      GotIt
    </IridescentButton>
  );
}

// Share buttons hand out a whole sentence, e.g. 【title】https://...?vd_source=...
// The backend normalises too; doing it here keeps the field forgiving.
function extractUrl(text: string): string {
  const match = text.match(/https?:\/\/[^\s<>"'\u3000-\u303f\uff00-\uffef]+/);
  return match ? match[0].replace(/[.,;:!?)\]}'"]+$/, "") : text.trim();
}

// The presets mirror the sections of prompts/summary_style.v1.md; the backend is
// the authority on what each one means, this table only labels them.
const STYLE_PRESETS: { id: SummaryStylePreset; label: string; hint: string }[] = [
  { id: "default", label: "Default", hint: "Balanced, no particular slant" },
  { id: "study_notes", label: "Study notes", hint: "Mechanisms, terms, cause and effect" },
  { id: "business_insight", label: "Business", hint: "Markets, numbers, what it changes" },
  { id: "debate", label: "Debate", hint: "Who disagrees, on what evidence" },
  { id: "quick_skim", label: "Quick skim", hint: "Only the load-bearing claims" }
];

// How much gets written, independent of the style presets above: style says how
// to write, detail says how much. "Standard" is what the summary prompts already
// describe, so it sends no directive at all.
const DETAIL_OPTIONS: { id: DetailLevel; label: string; hint: string }[] = [
  { id: "concise", label: "Brief", hint: "At most 3 key points per chapter, no chapter summary" },
  { id: "standard", label: "Standard", hint: "4–6 full key points per chapter, summary where it helps" },
  { id: "detailed", label: "Detailed", hint: "6–8 key points per chapter, every distinct example kept" }
];

function SubmitForm({ onSubmitted }: { onSubmitted: () => void }) {
  const { setOpen } = useModalControls();
  const [files, setFiles] = useState<File[]>([]);
  const [audioUrl, setAudioUrl] = useState("");
  const [ytSingle, setYtSingle] = useState("");
  const [ytBatch, setYtBatch] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState("upload");
  const [preset, setPreset] = useState<SummaryStylePreset>("default");
  const [note, setNote] = useState("");
  const [detail, setDetail] = useState<DetailLevel>("standard");
  const [styleOpen, setStyleOpen] = useState(false);

  const styled = preset !== "default" || note.trim().length > 0 || detail !== "standard";
  const style: SummaryStyleInput = {
    summary_style: preset,
    style_note: note.trim() || undefined,
    detail_level: detail
  };

  const onSubmit = async () => {
    setError(null);
    setBusy(true);
    try {
      if (tab === "upload") {
        if (files.length === 0) throw new Error("Choose at least one file");
        const inputs: CreateEpisodeInput[] = files.map((f) => ({
          source_type: "local_file",
          file: f,
          ...style
        }));
        if (inputs.length === 1) await createEpisode(inputs[0]);
        else await createEpisodeBatch(inputs);
      } else if (tab === "url") {
        if (!audioUrl.trim()) throw new Error("Enter an audio URL");
        await createEpisode({
          source_type: "direct_url",
          source_ref: audioUrl.trim(),
          ...style
        });
      } else if (tab === "youtube") {
        const single = ytSingle.trim();
        const batch = ytBatch
          .split("\n")
          .map((l) => l.trim())
          .filter(Boolean);
        if (!single && batch.length === 0) throw new Error("Enter a video link");
        if (single) {
          await createEpisode({
            source_type: "youtube",
            source_ref: extractUrl(single),
            ...style
          });
        }
        if (batch.length > 0) {
          await createEpisodeBatch(
            batch.map((url) => ({
              source_type: "youtube",
              source_ref: extractUrl(url),
              ...style
            }))
          );
        }
      }
      setOpen(false);
      onSubmitted();
      setFiles([]);
      setAudioUrl("");
      setYtSingle("");
      setYtBatch("");
    } catch (e) {
      const msg =
        e instanceof ApiError ? `${e.code}: ${e.message}` : e instanceof Error ? e.message : "Submission failed";
      setError(msg);
    } finally {
      setBusy(false);
    }
  };

  const presetLabel = STYLE_PRESETS.find((p) => p.id === preset)?.label ?? "Default";
  const detailLabel = DETAIL_OPTIONS.find((d) => d.id === detail)?.label ?? "Standard";
  const activeLabel = detail === "standard" ? presetLabel : `${presetLabel} · ${detailLabel}`;

  return (
    <>
      <ModalContent>
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="font-display text-xl font-semibold tracking-tight">
              Add a new episode
            </h2>
            <p className="mt-1 text-sm text-text-muted">
              Choose where the audio comes from. Processing runs in the background.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setStyleOpen((open) => !open)}
            aria-expanded={styleOpen}
            className={`flex shrink-0 items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
              styled
                ? "border-text/30 bg-surface-elev text-text"
                : "border-border text-text-muted hover:border-text/30 hover:text-text"
            }`}
          >
            <SlidersHorizontal className="h-3.5 w-3.5" strokeWidth={2.2} />
            {styled ? activeLabel : "Summary style"}
          </button>
        </div>

        {styleOpen && (
          <div className="mt-4 rounded-2xl bg-surface-elev p-4">
            <div className="flex flex-wrap gap-2">
              {STYLE_PRESETS.map((option) => (
                <button
                  key={option.id}
                  type="button"
                  title={option.hint}
                  onClick={() => setPreset(option.id)}
                  className={`rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
                    preset === option.id
                      ? "bg-text text-white"
                      : "bg-surface text-text-muted hover:text-text"
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
            <p className="mt-2 text-xs text-text-muted">
              {STYLE_PRESETS.find((p) => p.id === preset)?.hint}
            </p>
            <div className="mt-3 flex items-center gap-3">
              <span className="text-xs font-medium text-text-muted">Detail</span>
              <div className="inline-flex rounded-full bg-surface p-0.5">
                {DETAIL_OPTIONS.map((option) => (
                  <button
                    key={option.id}
                    type="button"
                    title={option.hint}
                    onClick={() => setDetail(option.id)}
                    className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                      detail === option.id
                        ? "bg-text text-white"
                        : "text-text-muted hover:text-text"
                    }`}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>
            <p className="mt-2 text-xs text-text-muted">
              {DETAIL_OPTIONS.find((d) => d.id === detail)?.hint}
            </p>
            <textarea
              rows={2}
              maxLength={STYLE_NOTE_MAX_CHARS}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Optional: one more instruction, e.g. lean on methodology, skip the personal anecdotes"
              className="mt-3 w-full resize-none rounded-lg border border-border bg-surface px-3 py-2 text-sm outline-none focus:border-text/40"
            />
            <div className="mt-2 flex items-center justify-between text-xs text-text-muted">
              <span>
                Style shapes tone, emphasis and depth only — the summary keeps its
                structure and stays faithful to the episode.
              </span>
              <span className="ml-3 shrink-0 tabular-nums">
                {note.length}/{STYLE_NOTE_MAX_CHARS}
              </span>
            </div>
            {styled && (
              <button
                type="button"
                onClick={() => {
                  setPreset("default");
                  setNote("");
                  setDetail("standard");
                }}
                className="mt-2 text-xs font-medium text-text-muted underline-offset-2 hover:text-text hover:underline"
              >
                Reset to default
              </button>
            )}
          </div>
        )}

        <div className="mt-6">
          <Tabs
            onChange={setTab}
            items={[
              {
                id: "upload",
                label: "Upload",
                content: <FileUpload onFiles={setFiles} />
              },
              {
                id: "url",
                label: "Audio URL",
                content: (
                  <input
                    autoFocus
                    type="url"
                    placeholder="https://example.com/episode.mp3"
                    value={audioUrl}
                    onChange={(e) => setAudioUrl(e.target.value)}
                    className="w-full rounded-xl border border-border bg-surface px-4 py-3 text-sm outline-none transition-colors focus:border-text/40 focus:bg-white"
                  />
                )
              },
              {
                id: "youtube",
                label: "Video Link",
                content: (
                  <div className="space-y-3">
                    <input
                      // Not type="url": a pasted share string reads as
                      // 【title】https://... and would fail native validation.
                      type="text"
                      placeholder="YouTube or Bilibili link — 【title】https://... is fine"
                      value={ytSingle}
                      onChange={(e) => setYtSingle(e.target.value)}
                      className="w-full rounded-xl border border-border bg-surface px-4 py-3 text-sm outline-none transition-colors focus:border-text/40 focus:bg-white"
                    />
                    <details className="rounded-xl bg-surface-elev p-3">
                      <summary className="cursor-pointer text-xs font-medium text-text-muted">
                        Batch (one link per line)
                      </summary>
                      <textarea
                        rows={4}
                        placeholder="https://...&#10;https://..."
                        value={ytBatch}
                        onChange={(e) => setYtBatch(e.target.value)}
                        className="mt-2 w-full resize-none rounded-lg border border-border bg-surface px-3 py-2 text-sm outline-none focus:border-text/40"
                      />
                    </details>
                  </div>
                )
              }
            ]}
          />
        </div>
        {error && (
          <div className="mt-4 rounded-lg bg-status-err/10 px-3 py-2 text-sm text-status-err">
            {error}
          </div>
        )}
      </ModalContent>
      <ModalFooter>
        <button
          type="button"
          onClick={() => setOpen(false)}
          className="rounded-full px-4 py-2 text-sm font-medium text-text-muted hover:text-text"
        >
          Cancel
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={onSubmit}
          className="rounded-full bg-text px-5 py-2 text-sm font-medium text-white shadow-card transition-opacity hover:opacity-90 disabled:opacity-50"
        >
          {busy ? "Submitting…" : "Add to queue"}
        </button>
      </ModalFooter>
    </>
  );
}
