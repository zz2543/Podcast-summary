import { AlignLeft, Download, FileJson, FileText, MessageCircle, Music, RotateCw, Trash2 } from "lucide-react";
import { FloatingDock, type DockItem } from "@/components/ui/floating-dock";
import { episodeFileUrl, type EpisodeDetail } from "@/api/client";

export function EpisodeDock({
  episode,
  onRetry,
  onDelete,
  onChatToggle,
  chatOpen,
  busy
}: {
  episode: EpisodeDetail;
  onRetry: () => void;
  onDelete: () => void;
  onChatToggle: () => void;
  chatOpen: boolean;
  busy: boolean;
}) {
  const items: DockItem[] = [
    {
      id: "retry",
      icon: <RotateCw className="h-5 w-5" strokeWidth={1.6} />,
      label: busy ? "Working…" : "Retry",
      onClick: onRetry,
      disabled: busy
    },
    {
      id: "md",
      icon: <FileText className="h-5 w-5" strokeWidth={1.6} />,
      label: "Markdown",
      onClick: () => window.open(episodeFileUrl(episode.id, "markdown"), "_blank"),
      disabled: !episode.artifact_paths?.markdown
    },
    {
      id: "json",
      icon: <FileJson className="h-5 w-5" strokeWidth={1.6} />,
      label: "JSON",
      onClick: () => window.open(episodeFileUrl(episode.id, "json"), "_blank"),
      disabled: !episode.artifact_paths?.json
    },
    {
      id: "transcript",
      icon: <AlignLeft className="h-5 w-5" strokeWidth={1.6} />,
      label: "导出文稿",
      onClick: () => window.open(episodeFileUrl(episode.id, "transcript"), "_blank")
    },
    {
      id: "audio",
      icon: <Music className="h-5 w-5" strokeWidth={1.6} />,
      label: "Original audio",
      onClick: () => window.open(episodeFileUrl(episode.id, "audio"), "_blank")
    },
    {
      id: "digest",
      icon: <Download className="h-5 w-5" strokeWidth={1.6} />,
      label: "Audio digest",
      onClick: () => window.open(episodeFileUrl(episode.id, "digest"), "_blank"),
      disabled: episode.stage_status.tts !== "present"
    },
    {
      id: "chat",
      icon: <MessageCircle className="h-5 w-5" strokeWidth={1.6} />,
      label: chatOpen ? "关闭对话" : "与文稿对话",
      onClick: onChatToggle,
      variant: chatOpen ? "active" as "default" : "default"
    },
    {
      id: "delete",
      icon: <Trash2 className="h-5 w-5" strokeWidth={1.6} />,
      label: "Delete",
      onClick: onDelete,
      variant: "danger"
    }
  ];
  return <FloatingDock items={items} />;
}
