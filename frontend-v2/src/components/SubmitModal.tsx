import { Plus } from "lucide-react";
import { useState } from "react";
import {
  Modal,
  ModalBody,
  ModalContent,
  ModalFooter,
  ModalTrigger,
  useModalControls
} from "@/components/ui/animated-modal";
import { Tabs } from "@/components/ui/tabs";
import { FileUpload } from "@/components/ui/file-upload";
import {
  ApiError,
  createEpisode,
  createEpisodeBatch,
  type CreateEpisodeInput
} from "@/api/client";

export function SubmitModal({ onSubmitted }: { onSubmitted: () => void }) {
  return (
    <Modal>
      <ModalTrigger className="inline-flex items-center gap-1.5 rounded-full bg-text px-4 py-2 text-sm font-medium text-white shadow-card transition-transform hover:-translate-y-px hover:shadow-card-hover">
        <Plus className="h-4 w-4" strokeWidth={2.2} />
        New Episode
      </ModalTrigger>
      <ModalBody>
        <SubmitForm onSubmitted={onSubmitted} />
      </ModalBody>
    </Modal>
  );
}

function SubmitForm({ onSubmitted }: { onSubmitted: () => void }) {
  const { setOpen } = useModalControls();
  const [files, setFiles] = useState<File[]>([]);
  const [audioUrl, setAudioUrl] = useState("");
  const [ytSingle, setYtSingle] = useState("");
  const [ytBatch, setYtBatch] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState("upload");

  const onSubmit = async () => {
    setError(null);
    setBusy(true);
    try {
      if (tab === "upload") {
        if (files.length === 0) throw new Error("Choose at least one file");
        const inputs: CreateEpisodeInput[] = files.map((f) => ({
          source_type: "local_file",
          file: f
        }));
        if (inputs.length === 1) await createEpisode(inputs[0]);
        else await createEpisodeBatch(inputs);
      } else if (tab === "url") {
        if (!audioUrl.trim()) throw new Error("Enter an audio URL");
        await createEpisode({ source_type: "direct_url", source_ref: audioUrl.trim() });
      } else if (tab === "youtube") {
        const single = ytSingle.trim();
        const batch = ytBatch
          .split("\n")
          .map((l) => l.trim())
          .filter(Boolean);
        if (!single && batch.length === 0) throw new Error("Enter a YouTube URL");
        if (single) {
          await createEpisode({ source_type: "youtube", source_ref: single });
        }
        if (batch.length > 0) {
          await createEpisodeBatch(
            batch.map((url) => ({ source_type: "youtube", source_ref: url }))
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

  return (
    <>
      <ModalContent>
        <h2 className="font-display text-xl font-semibold tracking-tight">
          Add a new episode
        </h2>
        <p className="mt-1 text-sm text-text-muted">
          Choose where the audio comes from. Processing runs in the background.
        </p>
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
                label: "YouTube",
                content: (
                  <div className="space-y-3">
                    <input
                      type="url"
                      placeholder="https://www.youtube.com/watch?v=..."
                      value={ytSingle}
                      onChange={(e) => setYtSingle(e.target.value)}
                      className="w-full rounded-xl border border-border bg-surface px-4 py-3 text-sm outline-none transition-colors focus:border-text/40 focus:bg-white"
                    />
                    <details className="rounded-xl bg-surface-elev p-3">
                      <summary className="cursor-pointer text-xs font-medium text-text-muted">
                        Batch (one URL per line)
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
