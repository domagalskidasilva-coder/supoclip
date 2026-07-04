"use client";

import Image from "next/image";
import Link from "next/link";
import type { ChangeEvent, FormEvent } from "react";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  CheckCircle,
  Film,
  FolderClock,
  Loader2,
  Palette,
  Settings,
  SlidersHorizontal,
  Timer,
  Type,
  Upload,
  Youtube,
} from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { track } from "@/lib/datafast";
import { formatSupportMessage, parseApiError } from "@/lib/api-error";

interface FontOption {
  name: string;
  display_name: string;
  format?: string;
}

interface TemplateOption {
  id: string;
  name: string;
  description: string;
  animation: string;
  font_family?: string;
  font_size?: number;
  font_color?: string;
}

interface TaskSummary {
  id: string;
  source_title: string;
  source_type: string;
  status: string;
  clips_count: number;
  created_at: string;
}

type SourceType = "youtube" | "upload";
type OutputFormat = "vertical" | "vertical_pan" | "vertical_split" | "original";

type UploadAuthorization = {
  directUpload: boolean;
  uploadUrl?: string;
  headers?: Record<string, string>;
};

const MAX_VIDEO_UPLOAD_BYTES = 1_000_000_000;

async function uploadVideoFile(file: File): Promise<string> {
  if (file.size > MAX_VIDEO_UPLOAD_BYTES) {
    throw new Error("O arquivo é grande demais. Envie um vídeo com menos de 1 GB.");
  }

  const authorizationResponse = await fetch("/api/upload/authorization", {
    method: "POST",
    cache: "no-store",
  });

  if (!authorizationResponse.ok) {
    const parsed = await parseApiError(
      authorizationResponse,
      `Erro na autorização do upload: ${authorizationResponse.status}`,
    );
    throw new Error(formatSupportMessage(parsed));
  }

  const authorization = (await authorizationResponse.json()) as UploadAuthorization;
  const formData = new FormData();
  formData.append("video", file);

  const uploadResponse = await fetch(
    authorization.directUpload && authorization.uploadUrl ? authorization.uploadUrl : "/api/upload",
    {
      method: "POST",
      headers: authorization.headers ?? {},
      body: formData,
    },
  );

  if (!uploadResponse.ok) {
    const parsed = await parseApiError(uploadResponse, `Erro no upload: ${uploadResponse.status}`);
    throw new Error(formatSupportMessage(parsed));
  }

  const uploadResult = await uploadResponse.json();
  if (typeof uploadResult.video_path !== "string" || !uploadResult.video_path) {
    throw new Error("O upload terminou sem retornar o vídeo. Tente novamente.");
  }

  return uploadResult.video_path;
}

function formatDate(value: string) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "Desconhecido";
  return new Intl.DateTimeFormat("pt-BR", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(parsed);
}

const STATUS_LABELS: Record<string, string> = {
  completed: "concluído",
  error: "erro",
  cancelled: "cancelado",
  processing: "processando",
  queued: "na fila",
  pending: "pendente",
};

function statusLabel(status: string) {
  return STATUS_LABELS[status] ?? status;
}

function statusTone(status: string) {
  if (status === "completed") return "bg-emerald-50 text-emerald-700 border-emerald-200";
  if (status === "error") return "bg-red-50 text-red-700 border-red-200";
  if (status === "cancelled") return "bg-stone-100 text-stone-600 border-stone-200";
  return "bg-blue-50 text-blue-700 border-blue-200";
}

export default function Home() {
  const [sourceType, setSourceType] = useState<SourceType>("youtube");
  const [url, setUrl] = useState("");
  const [fileName, setFileName] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recentTasks, setRecentTasks] = useState<TaskSummary[]>([]);
  const [isLoadingTasks, setIsLoadingTasks] = useState(true);

  const [fontFamily, setFontFamily] = useState("THEBOLDFONT");
  const [fontSize, setFontSize] = useState(32);
  const [fontColor, setFontColor] = useState("#FFFFFF");
  const [captionTemplate, setCaptionTemplate] = useState("default");
  const [includeBroll, setIncludeBroll] = useState(false);
  const [outputFormat, setOutputFormat] = useState<OutputFormat>("vertical");
  const [clipDuration, setClipDuration] = useState(30);
  const [addSubtitles, setAddSubtitles] = useState(true);
  const [cutLongPauses, setCutLongPauses] = useState(true);
  const [pauseThresholdMs, setPauseThresholdMs] = useState("800");
  const [removeFillerWords, setRemoveFillerWords] = useState(false);
  const [filteredWords, setFilteredWords] = useState("");
  const [availableFonts, setAvailableFonts] = useState<FontOption[]>([]);
  const [availableTemplates, setAvailableTemplates] = useState<TemplateOption[]>([]);
  const [brollAvailable, setBrollAvailable] = useState(false);

  const fileRef = useRef<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const loadRecentTasks = useCallback(async () => {
    try {
      setIsLoadingTasks(true);
      const response = await fetch("/api/tasks/", { cache: "no-store" });
      if (!response.ok) return;
      const data = await response.json();
      setRecentTasks((data.tasks || []).slice(0, 5));
    } finally {
      setIsLoadingTasks(false);
    }
  }, []);

  useEffect(() => {
    const rawPreferences = window.localStorage.getItem("supoclip.preferences");
    if (rawPreferences) {
      try {
        const preferences = JSON.parse(rawPreferences) as {
          fontFamily?: string;
          fontSize?: number;
          fontColor?: string;
        };
        if (preferences.fontFamily) setFontFamily(preferences.fontFamily);
        if (typeof preferences.fontSize === "number") setFontSize(preferences.fontSize);
        if (preferences.fontColor) setFontColor(preferences.fontColor);
      } catch {
        window.localStorage.removeItem("supoclip.preferences");
      }
    }

    void loadRecentTasks();
  }, [loadRecentTasks]);

  useEffect(() => {
    async function loadOptions() {
      try {
        const [fontsResponse, templatesResponse, brollResponse] = await Promise.all([
          fetch("/api/fonts", { cache: "no-store" }),
          fetch(`${apiUrl}/caption-templates`, { cache: "no-store" }),
          fetch(`${apiUrl}/broll/status`, { cache: "no-store" }),
        ]);

        if (fontsResponse.ok) {
          const data = await fontsResponse.json();
          const fonts = (data.fonts || []) as FontOption[];
          setAvailableFonts(fonts);

          const styleElement = document.createElement("style");
          styleElement.id = "custom-fonts";
          styleElement.innerHTML = fonts
            .map((font) => {
              const format = font.format === "otf" ? "opentype" : "truetype";
              return `@font-face{font-family:'${font.name}';src:url('/api/fonts/${font.name}') format('${format}');font-weight:normal;font-style:normal;}`;
            })
            .join("\n");

          document.getElementById("custom-fonts")?.remove();
          document.head.appendChild(styleElement);
        }

        if (templatesResponse.ok) {
          const data = await templatesResponse.json();
          setAvailableTemplates(data.templates || []);
        }

        if (brollResponse.ok) {
          const data = await brollResponse.json();
          setBrollAvailable(Boolean(data.configured));
        }
      } catch (loadError) {
        console.error("Failed to load app options:", loadError);
      }
    }

    void loadOptions();
  }, [apiUrl]);

  const handleTemplateChange = (templateId: string) => {
    setCaptionTemplate(templateId);
    const selected = availableTemplates.find((template) => template.id === templateId);
    if (!selected) return;
    if (selected.font_family) setFontFamily(selected.font_family);
    if (typeof selected.font_size === "number") setFontSize(selected.font_size);
    if (selected.font_color) setFontColor(selected.font_color);
  };

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] ?? null;
    fileRef.current = file;
    setFileName(file?.name ?? null);
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (sourceType === "youtube" && !url.trim()) return;
    if (sourceType === "upload" && !fileRef.current) return;

    setIsSubmitting(true);
    setError(null);

    try {
      let sourceUrl = url.trim();
      if (sourceType === "upload" && fileRef.current) {
        sourceUrl = await uploadVideoFile(fileRef.current);
      }

      const normalizedPauseThreshold = Number.isFinite(Number(pauseThresholdMs))
        ? Math.max(250, Math.min(3000, Math.round(Number(pauseThresholdMs))))
        : 800;
      const normalizedFilteredWords = filteredWords
        .split(",")
        .map((word) => word.trim().toLowerCase())
        .filter(Boolean);
      const normalizedClipDuration = Math.max(15, Math.min(90, Math.round(clipDuration)));

      const response = await fetch("/api/tasks/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source: { url: sourceUrl, title: null },
          font_options: {
            font_family: fontFamily,
            font_size: fontSize,
            font_color: /^#[0-9A-Fa-f]{6}$/.test(fontColor) ? fontColor : "#FFFFFF",
          },
          caption_template: captionTemplate,
          include_broll: includeBroll,
          processing_mode: "fast",
          output_format: outputFormat,
          clip_duration: normalizedClipDuration,
          add_subtitles: addSubtitles,
          cut_long_pauses: cutLongPauses,
          pause_threshold_ms: normalizedPauseThreshold,
          remove_filler_words: removeFillerWords,
          filtered_words: normalizedFilteredWords,
        }),
      });

      if (!response.ok) {
        const parsed = await parseApiError(response, `API error: ${response.status}`);
        throw new Error(formatSupportMessage(parsed));
      }

      const result = await response.json();
      track("task_created", {
        source_type: sourceType,
        caption_template: captionTemplate,
        include_broll: includeBroll,
        output_format: outputFormat,
        clip_duration: normalizedClipDuration,
        add_subtitles: addSubtitles,
      });
      window.location.href = `/tasks/${result.task_id}`;
    } catch (submitError) {
      console.error("Error creating task:", submitError);
      setError(submitError instanceof Error ? submitError.message : "Não foi possível processar o vídeo.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="min-h-screen bg-stone-50">
      <header className="border-b border-stone-200 bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-4">
          <Link href="/" className="flex items-center gap-3">
            <Image src="/logo.png" alt="SupoClip" width={28} height={28} className="rounded-md" />
            <span className="font-[var(--font-syne)] text-xl font-bold text-stone-950">SupoClip</span>
          </Link>
          <nav className="flex items-center gap-2">
            <Link href="/list">
              <Button variant="outline" size="sm">
                <FolderClock className="h-4 w-4" />
                Meus cortes
              </Button>
            </Link>
            <Link href="/settings">
              <Button variant="outline" size="sm">
                <Settings className="h-4 w-4" />
                Configurações
              </Button>
            </Link>
          </nav>
        </div>
      </header>

      <div className="mx-auto grid max-w-7xl gap-6 px-4 py-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <section className="space-y-6">
          <div>
            <h1 className="font-[var(--font-syne)] text-3xl font-bold tracking-tight text-stone-950">
              Cole o link, receba os cortes
            </h1>
            <p className="mt-2 max-w-2xl text-sm text-stone-600">
              Cole um link do YouTube ou envie um vídeo. A IA encontra os melhores momentos e
              entrega cortes verticais com legendas, prontos para TikTok, Reels e Shorts.
            </p>
          </div>

          <Card className="border-stone-200">
            <CardContent className="p-5">
              <form className="space-y-6" onSubmit={handleSubmit}>
                <div className="grid gap-2 sm:grid-cols-2">
                  <Button
                    type="button"
                    variant={sourceType === "youtube" ? "default" : "outline"}
                    onClick={() => setSourceType("youtube")}
                    className="justify-start"
                  >
                    <Youtube className="h-4 w-4" />
                    Link do YouTube
                  </Button>
                  <Button
                    type="button"
                    variant={sourceType === "upload" ? "default" : "outline"}
                    onClick={() => setSourceType("upload")}
                    className="justify-start"
                  >
                    <Upload className="h-4 w-4" />
                    Enviar vídeo
                  </Button>
                </div>

                {sourceType === "youtube" ? (
                  <div className="space-y-2">
                    <Label htmlFor="video-url">Link do vídeo</Label>
                    <Input
                      id="video-url"
                      value={url}
                      onChange={(event) => setUrl(event.target.value)}
                      placeholder="https://www.youtube.com/watch?v=..."
                      disabled={isSubmitting}
                    />
                  </div>
                ) : (
                  <div className="space-y-2">
                    <Label htmlFor="video-file">Arquivo de vídeo</Label>
                    <Input
                      id="video-file"
                      ref={fileInputRef}
                      type="file"
                      accept="video/*"
                      onChange={handleFileChange}
                      disabled={isSubmitting}
                    />
                    {fileName ? <p className="text-xs text-stone-500">{fileName}</p> : null}
                  </div>
                )}

                <Separator />

                <div className="grid gap-4 lg:grid-cols-2">
                  <div className="space-y-2">
                    <Label className="flex items-center gap-2">
                      <Type className="h-4 w-4" />
                      Fonte
                    </Label>
                    <Select value={fontFamily} onValueChange={setFontFamily} disabled={isSubmitting}>
                      <SelectTrigger>
                        <SelectValue placeholder="Escolha a fonte" />
                      </SelectTrigger>
                      <SelectContent>
                        {availableFonts.map((font) => (
                          <SelectItem key={font.name} value={font.name}>
                            {font.display_name}
                          </SelectItem>
                        ))}
                        {availableFonts.length === 0 ? (
                          <SelectItem value="THEBOLDFONT">The Bold Font</SelectItem>
                        ) : null}
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-2">
                    <Label>Estilo de legenda</Label>
                    <Select value={captionTemplate} onValueChange={handleTemplateChange} disabled={isSubmitting}>
                      <SelectTrigger>
                        <SelectValue placeholder="Estilo" />
                      </SelectTrigger>
                      <SelectContent>
                        {availableTemplates.map((template) => (
                          <SelectItem key={template.id} value={template.id}>
                            {template.name}
                          </SelectItem>
                        ))}
                        {availableTemplates.length === 0 ? (
                          <SelectItem value="default">Padrão</SelectItem>
                        ) : null}
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-2">
                    <Label>Tamanho da fonte: {fontSize}px</Label>
                    <Slider
                      value={[fontSize]}
                      min={12}
                      max={72}
                      step={2}
                      disabled={isSubmitting}
                      onValueChange={(value) => setFontSize(value[0])}
                    />
                  </div>

                  <div className="space-y-2">
                    <Label className="flex items-center gap-2">
                      <Palette className="h-4 w-4" />
                      Cor
                    </Label>
                    <div className="flex gap-2">
                      <Input
                        value={fontColor}
                        onChange={(event) => setFontColor(event.target.value)}
                        disabled={isSubmitting}
                      />
                      <input
                        aria-label="Cor da legenda"
                        type="color"
                        value={fontColor}
                        onChange={(event) => setFontColor(event.target.value)}
                        disabled={isSubmitting}
                        className="h-10 w-12 rounded-md border border-stone-300 bg-white"
                      />
                    </div>
                  </div>
                </div>

                <div className="grid gap-4 lg:grid-cols-2">
                  <div className="space-y-2">
                    <Label>Formato de saída</Label>
                    <Select value={outputFormat} onValueChange={(value) => setOutputFormat(value as OutputFormat)}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="vertical">Vertical (foco no rosto)</SelectItem>
                        <SelectItem value="vertical_pan">Vertical (câmera acompanha)</SelectItem>
                        <SelectItem value="vertical_split">Vertical (tela dividida)</SelectItem>
                        <SelectItem value="original">Original (mais rápido)</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-2">
                    <Label className="flex items-center gap-2">
                      <Timer className="h-4 w-4" />
                      Duração alvo do corte: {clipDuration}s
                    </Label>
                    <div className="flex items-center gap-3">
                      <Slider
                        value={[clipDuration]}
                        min={15}
                        max={90}
                        step={5}
                        disabled={isSubmitting}
                        onValueChange={(value) => setClipDuration(value[0])}
                      />
                      <Input
                        aria-label="Duração do corte em segundos"
                        type="number"
                        min={15}
                        max={90}
                        step={5}
                        value={clipDuration}
                        onChange={(event) => {
                          const nextValue = Number(event.target.value);
                          if (Number.isFinite(nextValue)) {
                            setClipDuration(Math.max(15, Math.min(90, Math.round(nextValue))));
                          }
                        }}
                        disabled={isSubmitting}
                        className="w-20"
                      />
                    </div>
                  </div>

                  <div className="space-y-3 rounded-md border border-stone-200 p-3">
                    <div className="flex items-center justify-between gap-3">
                      <Label htmlFor="add-subtitles">Legendas automáticas</Label>
                      <Switch id="add-subtitles" checked={addSubtitles} onCheckedChange={setAddSubtitles} />
                    </div>
                    <div className="flex items-center justify-between gap-3">
                      <Label htmlFor="include-broll">B-roll (imagens de apoio)</Label>
                      <Switch
                        id="include-broll"
                        checked={includeBroll}
                        onCheckedChange={setIncludeBroll}
                        disabled={!brollAvailable}
                      />
                    </div>
                  </div>
                </div>

                <details className="rounded-md border border-stone-200 bg-stone-50 p-3">
                  <summary className="flex cursor-pointer items-center gap-2 text-sm font-medium text-stone-900">
                    <SlidersHorizontal className="h-4 w-4" />
                    Limpeza automática
                  </summary>
                  <div className="mt-4 grid gap-4 lg:grid-cols-2">
                    <div className="flex items-center justify-between gap-3">
                      <Label htmlFor="cut-pauses">Cortar pausas e silêncios</Label>
                      <Switch id="cut-pauses" checked={cutLongPauses} onCheckedChange={setCutLongPauses} />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="pause-threshold">Limite de pausa (ms)</Label>
                      <Input
                        id="pause-threshold"
                        value={pauseThresholdMs}
                        onChange={(event) => setPauseThresholdMs(event.target.value)}
                      />
                    </div>
                    <div className="flex items-center justify-between gap-3">
                      <Label htmlFor="remove-fillers">Remover vícios de fala</Label>
                      <Switch id="remove-fillers" checked={removeFillerWords} onCheckedChange={setRemoveFillerWords} />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="filtered-words">Palavras para remover</Label>
                      <Textarea
                        id="filtered-words"
                        value={filteredWords}
                        onChange={(event) => setFilteredWords(event.target.value)}
                        placeholder="éé, hã, tipo assim"
                        rows={2}
                      />
                    </div>
                  </div>
                </details>

                {error ? (
                  <Alert className="border-red-200 bg-red-50">
                    <AlertCircle className="h-4 w-4 text-red-500" />
                    <AlertDescription className="text-sm text-red-700">{error}</AlertDescription>
                  </Alert>
                ) : null}

                <Button
                  type="submit"
                  className="h-11 w-full"
                  disabled={
                    isSubmitting ||
                    (sourceType === "youtube" && !url.trim()) ||
                    (sourceType === "upload" && !fileRef.current)
                  }
                >
                  {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Film className="h-4 w-4" />}
                  {isSubmitting ? "Enviando..." : "Gerar cortes"}
                </Button>
              </form>
            </CardContent>
          </Card>
        </section>

        <aside className="space-y-6">
          <Card className="border-stone-200">
            <CardContent className="p-5">
              <div className="mb-4 flex items-center justify-between">
                <h2 className="text-sm font-semibold uppercase tracking-wide text-stone-500">Prévia da legenda</h2>
                <Badge variant="outline">{outputFormat}</Badge>
              </div>
              <div className="flex aspect-[9/16] items-center justify-center rounded-md bg-stone-950 p-5">
                <p
                  className="text-center font-bold leading-tight"
                  style={{
                    color: fontColor,
                    fontFamily: `'${fontFamily}', system-ui, sans-serif`,
                    fontSize: `${Math.min(Math.max(fontSize, 12), 42)}px`,
                    textShadow: "0 2px 8px rgba(0,0,0,0.8)",
                  }}
                >
                  Sua legenda vai ficar assim
                </p>
              </div>
            </CardContent>
          </Card>

          <Card className="border-stone-200">
            <CardContent className="p-5">
              <div className="mb-4 flex items-center justify-between">
                <h2 className="text-sm font-semibold uppercase tracking-wide text-stone-500">Gerações recentes</h2>
                <Link href="/list" className="text-xs font-medium text-stone-900 underline underline-offset-4">
                  Ver todas
                </Link>
              </div>
              {isLoadingTasks ? (
                <div className="space-y-3 text-sm text-stone-500">Carregando...</div>
              ) : recentTasks.length === 0 ? (
                <div className="rounded-md border border-dashed border-stone-200 p-4 text-sm text-stone-500">
                  Nenhuma geração ainda. Cole um link e gere seus primeiros cortes.
                </div>
              ) : (
                <div className="space-y-2">
                  {recentTasks.map((task) => (
                    <Link
                      key={task.id}
                      href={`/tasks/${task.id}`}
                      className="block rounded-md border border-stone-200 bg-white p-3 transition-colors hover:bg-stone-50"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium text-stone-950">{task.source_title}</p>
                          <p className="mt-1 text-xs text-stone-500">{formatDate(task.created_at)}</p>
                        </div>
                        <span className={`rounded-full border px-2 py-0.5 text-xs ${statusTone(task.status)}`}>
                          {statusLabel(task.status)}
                        </span>
                      </div>
                      {task.status === "completed" ? (
                        <div className="mt-2 flex items-center gap-1.5 text-xs text-emerald-700">
                          <CheckCircle className="h-3.5 w-3.5" />
                          {task.clips_count} cortes prontos
                        </div>
                      ) : null}
                    </Link>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </aside>
      </div>
    </main>
  );
}
