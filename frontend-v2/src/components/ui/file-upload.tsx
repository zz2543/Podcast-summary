import { motion } from "framer-motion";
import { UploadCloud } from "lucide-react";
import { useRef, useState } from "react";
import { cn } from "@/lib/cn";

export function FileUpload({
  onFiles,
  multiple = true,
  accept = "audio/*",
  className
}: {
  onFiles: (files: File[]) => void;
  multiple?: boolean;
  accept?: string;
  className?: string;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [picked, setPicked] = useState<File[]>([]);

  const handle = (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const list = Array.from(files);
    setPicked(list);
    onFiles(list);
  };

  return (
    <div
      className={cn(
        "relative w-full cursor-pointer rounded-2xl border border-dashed transition-all",
        dragOver
          ? "border-text bg-surface-elev shadow-card-hover"
          : "border-border bg-surface hover:border-text/30 hover:shadow-card",
        className
      )}
      onClick={() => inputRef.current?.click()}
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        handle(e.dataTransfer.files);
      }}
    >
      <input
        ref={inputRef}
        type="file"
        multiple={multiple}
        accept={accept}
        className="hidden"
        onChange={(e) => handle(e.target.files)}
      />
      <motion.div
        animate={{ y: dragOver ? -2 : 0 }}
        className="flex flex-col items-center justify-center px-6 py-12 text-center"
      >
        <UploadCloud className="mb-3 h-7 w-7 text-text-muted" strokeWidth={1.5} />
        <p className="text-sm font-medium text-text">
          {picked.length > 0
            ? `${picked.length} file${picked.length > 1 ? "s" : ""} selected`
            : "Drop audio files or click to choose"}
        </p>
        <p className="mt-1 text-xs text-text-subtle">
          MP3 · WAV · M4A · up to multiple at once
        </p>
        {picked.length > 0 && (
          <ul className="mt-4 max-h-32 w-full overflow-auto rounded-lg bg-surface-elev px-3 py-2 text-left text-xs text-text-muted scroll-area">
            {picked.map((f, i) => (
              <li key={i} className="truncate">
                {f.name}
              </li>
            ))}
          </ul>
        )}
      </motion.div>
    </div>
  );
}
