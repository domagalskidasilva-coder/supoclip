"use client";

import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Checkbox } from "@/components/ui/checkbox";
import { Separator } from "@/components/ui/separator";
import {
  Tooltip,
  TooltipTrigger,
  TooltipContent,
} from "@/components/ui/tooltip";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { formatSupportMessage, parseApiError } from "@/lib/api-error";
import { cn } from "@/lib/utils";
import {
  ArrowLeft,
  Clock,
  PlayCircle,
  AlertCircle,
  CheckCircle,
  Loader2,
  PauseCircle,
  RotateCcw,
  Trash2,
  X,
} from "lucide-react";
import Link from "next/link";

interface Task {
  id: string;
  source_id: string;
  source_title: string;
  source_type: string;
  status: string;
  clips_count: number;
  created_at: string;
  updated_at: string;
}

type BatchAction = "cancel" | "resume" | "delete" | null;

const ACTIVE_TASK_STATUSES = ["queued", "processing"];
const RESUMABLE_TASK_STATUSES = ["cancelled", "error"];

async function fetchTasksList() {
  const response = await fetch("/api/tasks/", {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`Erro ao buscar as gerações: ${response.status}`);
  }

  const data = await response.json();
  return (data.tasks || []) as Task[];
}

async function buildSupportError(response: Response, fallbackMessage: string) {
  const parsed = await parseApiError(response, fallbackMessage);
  return formatSupportMessage(parsed);
}

const STATUS_CONFIG: Record<
  string,
  { label: string; dotClass: string; bgClass: string; textClass: string }
> = {
  completed: {
    label: "Concluído",
    dotClass: "bg-emerald-500",
    bgClass: "bg-emerald-50 border-emerald-200/60",
    textClass: "text-emerald-800",
  },
  processing: {
    label: "Processando",
    dotClass: "bg-blue-500 animate-pulse",
    bgClass: "bg-blue-50 border-blue-200/60",
    textClass: "text-blue-800",
  },
  queued: {
    label: "Na fila",
    dotClass: "bg-amber-500",
    bgClass: "bg-amber-50 border-amber-200/60",
    textClass: "text-amber-800",
  },
  error: {
    label: "Erro",
    dotClass: "bg-red-500",
    bgClass: "bg-red-50 border-red-200/60",
    textClass: "text-red-800",
  },
  cancelled: {
    label: "Cancelado",
    dotClass: "bg-stone-400",
    bgClass: "bg-stone-100 border-stone-200/60",
    textClass: "text-stone-600",
  },
};

export default function ListPage() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [selectedTaskIds, setSelectedTaskIds] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [batchNotice, setBatchNotice] = useState<{
    tone: "success" | "error";
    message: string;
  } | null>(null);
  const [activeBatchAction, setActiveBatchAction] = useState<BatchAction>(null);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);

  useEffect(() => {
    const loadTasks = async () => {
      try {
        setIsLoading(true);
        setError(null);
        const nextTasks = await fetchTasksList();
        setTasks(nextTasks);
        setSelectedTaskIds((current) =>
          current.filter((taskId) => nextTasks.some((task) => task.id === taskId)),
        );
      } catch (err) {
        console.error("Error fetching tasks:", err);
        setError(err instanceof Error ? err.message : "Não foi possível carregar as gerações");
      } finally {
        setIsLoading(false);
      }
    };

    void loadTasks();
  }, []);

  const refreshTasks = async () => {
    const nextTasks = await fetchTasksList();
    setTasks(nextTasks);
    setSelectedTaskIds((current) =>
      current.filter((taskId) => nextTasks.some((task) => task.id === taskId)),
    );
  };

  const selectedTasks = tasks.filter((task) => selectedTaskIds.includes(task.id));
  const selectedCount = selectedTasks.length;
  const completedCount = tasks.filter((task) => task.status === "completed").length;
  const activeCount = tasks.filter((task) => ACTIVE_TASK_STATUSES.includes(task.status)).length;
  const attentionCount = tasks.filter((task) => RESUMABLE_TASK_STATUSES.includes(task.status)).length;
  const cancelableCount = selectedTasks.filter((task) =>
    ACTIVE_TASK_STATUSES.includes(task.status),
  ).length;
  const resumableCount = selectedTasks.filter((task) =>
    RESUMABLE_TASK_STATUSES.includes(task.status),
  ).length;
  const allVisibleSelected = tasks.length > 0 && tasks.every((task) => selectedTaskIds.includes(task.id));
  const someSelected = selectedCount > 0 && !allVisibleSelected;

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return new Intl.DateTimeFormat("pt-BR", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }).format(date);
  };

  const handleToggleTask = (taskId: string) => {
    setBatchNotice(null);
    setSelectedTaskIds((current) => {
      if (current.includes(taskId)) {
        return current.filter((id) => id !== taskId);
      }
      return [...current, taskId];
    });
  };

  const handleToggleAllVisible = () => {
    setBatchNotice(null);
    if (allVisibleSelected) {
      setSelectedTaskIds([]);
      return;
    }
    setSelectedTaskIds(tasks.map((task) => task.id));
  };

  const runBatchAction = async (
    action: Exclude<BatchAction, null>,
    targetTaskIds: string[],
    requestFactory: (taskId: string) => Promise<Response>,
    labels: {
      empty: string;
      fallback: string;
      success: (count: number) => string;
      partial: (successCount: number, failureCount: number, firstError: string) => string;
    },
  ) => {
    if (targetTaskIds.length === 0) {
      setBatchNotice({ tone: "error", message: labels.empty });
      return;
    }

    setActiveBatchAction(action);
    setBatchNotice(null);

    const results = await Promise.allSettled(
      targetTaskIds.map(async (taskId) => {
        const response = await requestFactory(taskId);
        if (!response.ok) {
          throw new Error(await buildSupportError(response, labels.fallback));
        }
        return taskId;
      }),
    );

    const fulfilled = results.filter(
      (result): result is PromiseFulfilledResult<string> => result.status === "fulfilled",
    );
    const rejected = results.filter(
      (result): result is PromiseRejectedResult => result.status === "rejected",
    );

    try {
      if (fulfilled.length > 0) await refreshTasks();

      if (rejected.length === 0) {
        setBatchNotice({ tone: "success", message: labels.success(fulfilled.length) });
      } else {
        const firstFailure = rejected[0]?.reason;
        const firstError =
          firstFailure instanceof Error
            ? firstFailure.message
            : typeof firstFailure === "string"
              ? firstFailure
              : labels.fallback;
        setBatchNotice({
          tone: "error",
          message: labels.partial(fulfilled.length, rejected.length, firstError),
        });
      }
    } catch (refreshError) {
      console.error("Error refreshing task list:", refreshError);
      setBatchNotice({
        tone: "error",
        message:
          refreshError instanceof Error
            ? refreshError.message
            : "A ação em lote terminou, mas não foi possível atualizar a lista.",
      });
    } finally {
      setActiveBatchAction(null);
    }
  };

  const handleCancelSelected = async () => {
    const targetTaskIds = selectedTasks
      .filter((task) => ACTIVE_TASK_STATUSES.includes(task.status))
      .map((task) => task.id);

    await runBatchAction(
      "cancel",
      targetTaskIds,
      (taskId) => fetch(`/api/tasks/${taskId}/cancel`, { method: "POST" }),
      {
        empty: "Nenhuma geração ativa na seleção para cancelar.",
        fallback: "Não foi possível cancelar a geração",
        success: (count) => `${count} ${count === 1 ? "geração cancelada" : "gerações canceladas"}.`,
        partial: (s, f, err) => `${s} canceladas, ${f} falharam. ${err}`,
      },
    );
  };

  const handleResumeSelected = async () => {
    const targetTaskIds = selectedTasks
      .filter((task) => RESUMABLE_TASK_STATUSES.includes(task.status))
      .map((task) => task.id);

    await runBatchAction(
      "resume",
      targetTaskIds,
      (taskId) => fetch(`/api/tasks/${taskId}/resume`, { method: "POST" }),
      {
        empty: "Nenhuma geração com erro ou cancelada na seleção para retomar.",
        fallback: "Não foi possível retomar a geração",
        success: (count) => `${count} ${count === 1 ? "geração retomada" : "gerações retomadas"}.`,
        partial: (s, f, err) => `${s} retomadas, ${f} falharam. ${err}`,
      },
    );
  };

  const handleDeleteSelected = async () => {
    const targetTaskIds = [...selectedTaskIds];

    await runBatchAction(
      "delete",
      targetTaskIds,
      (taskId) => fetch(`/api/tasks/${taskId}`, { method: "DELETE" }),
      {
        empty: "Selecione pelo menos uma geração para excluir.",
        fallback: "Não foi possível excluir a geração",
        success: (count) => `${count} ${count === 1 ? "geração excluída" : "gerações excluídas"}.`,
        partial: (s, f, err) => `${s} excluídas, ${f} falharam. ${err}`,
      },
    );

    setShowDeleteDialog(false);
  };

  /* ── Loading / Auth gates ─────────────────────────────────── */

  /* ── Status badge renderer ────────────────────────────────── */

  const getStatusBadge = (status: string) => {
    const config = STATUS_CONFIG[status];
    if (!config) {
      return (
        <Badge variant="outline" className="capitalize">
          {status}
        </Badge>
      );
    }
    return (
      <span
        className={cn(
          "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium",
          config.bgClass,
          config.textClass,
        )}
      >
        <span className={cn("h-1.5 w-1.5 rounded-full", config.dotClass)} />
        {config.label}
      </span>
    );
  };

  /* ── Main render ──────────────────────────────────────────── */

  return (
    <div className="min-h-screen bg-stone-50/50">
      {/* ── Page header ──────────────────────────────────────── */}
      <div className="border-b border-stone-200 bg-white">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 py-5">
          <div className="flex items-center gap-3 mb-4">
            <Link href="/">
              <Button variant="ghost" size="sm" className="text-stone-500 hover:text-stone-900">
                <ArrowLeft className="w-4 h-4" />
                Voltar
              </Button>
            </Link>
          </div>

          <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h1 className="font-[var(--font-syne)] text-2xl font-bold tracking-tight text-stone-950">
                Meus cortes
              </h1>
              <p className="mt-1 text-sm text-stone-500">
                {tasks.length} no total &middot; gerencie e revise suas gerações
              </p>
            </div>

            {!isLoading && !error && tasks.length > 0 && (
              <div className="flex items-center gap-2">
                {completedCount > 0 && (
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 border border-emerald-200/60 px-2.5 py-1 text-xs font-medium text-emerald-800">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                    {completedCount} concluídas
                  </span>
                )}
                {activeCount > 0 && (
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-blue-50 border border-blue-200/60 px-2.5 py-1 text-xs font-medium text-blue-800">
                    <span className="h-1.5 w-1.5 rounded-full bg-blue-500 animate-pulse" />
                    {activeCount} em andamento
                  </span>
                )}
                {attentionCount > 0 && (
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-red-50 border border-red-200/60 px-2.5 py-1 text-xs font-medium text-red-700">
                    <span className="h-1.5 w-1.5 rounded-full bg-red-500" />
                    {attentionCount} precisam de atenção
                  </span>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Content ──────────────────────────────────────────── */}
      <div className={cn("max-w-5xl mx-auto px-4 sm:px-6 py-6", selectedCount > 0 && "pb-28")}>
        {/* Batch notice */}
        {batchNotice && (
          <Alert
            className={cn(
              "mb-4",
              batchNotice.tone === "success"
                ? "border-emerald-200 bg-emerald-50/50"
                : "border-red-200 bg-red-50/50",
            )}
          >
            {batchNotice.tone === "success" ? (
              <CheckCircle className="h-4 w-4 text-emerald-600" />
            ) : (
              <AlertCircle className="h-4 w-4 text-red-600" />
            )}
            <AlertDescription className="text-sm">
              {batchNotice.message}
            </AlertDescription>
          </Alert>
        )}

        {isLoading ? (
          <div className="space-y-3">
            {[1, 2, 3, 4].map((i) => (
              <div
                key={i}
                className="flex items-center gap-4 rounded-xl border border-stone-200 bg-white p-4"
              >
                <Skeleton className="h-5 w-5 rounded" />
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-4 w-64" />
                  <Skeleton className="h-3 w-40" />
                </div>
                <Skeleton className="h-6 w-20 rounded-full" />
              </div>
            ))}
          </div>
        ) : error ? (
          <Alert>
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : tasks.length === 0 ? (
          <Card className="border-stone-200">
            <CardContent className="p-12 text-center">
              <div className="w-16 h-16 bg-stone-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
                <PlayCircle className="w-8 h-8 text-stone-400" />
              </div>
              <h2 className="text-xl font-semibold text-stone-950 mb-2">Nenhuma geração ainda</h2>
              <p className="text-stone-500 mb-6 text-sm">
                Comece processando seu primeiro vídeo para criar cortes.
              </p>
              <Link href="/">
                <Button>Gerar cortes</Button>
              </Link>
            </CardContent>
          </Card>
        ) : (
          <>
            {/* ── Table header row ────────────────────────────── */}
            <div className="mb-2 flex items-center gap-4 px-4 py-2">
              <Checkbox
                checked={allVisibleSelected ? true : someSelected ? "indeterminate" : false}
                onCheckedChange={handleToggleAllVisible}
                disabled={activeBatchAction !== null}
                aria-label="Selecionar todas as gerações"
                className="data-[state=indeterminate]:bg-stone-400 data-[state=indeterminate]:border-stone-400"
              />
              <span className="text-xs font-medium uppercase tracking-widest text-stone-400">
                {selectedCount > 0 ? `${selectedCount} de ${tasks.length} selecionadas` : "Selecionar"}
              </span>
            </div>

            {/* ── Task list ───────────────────────────────────── */}
            <div className="space-y-2">
              {tasks.map((task) => {
                const isSelected = selectedTaskIds.includes(task.id);

                return (
                  <div
                    key={task.id}
                    className={cn(
                      "group relative flex items-start gap-4 rounded-xl border bg-white p-4 transition-all duration-150",
                      isSelected
                        ? "border-stone-900/20 bg-stone-50 shadow-sm ring-1 ring-stone-900/5"
                        : "border-stone-200 hover:border-stone-300 hover:shadow-sm",
                    )}
                  >
                    {/* Selection indicator bar */}
                    <div
                      className={cn(
                        "absolute left-0 top-3 bottom-3 w-0.5 rounded-full transition-all duration-150",
                        isSelected ? "bg-stone-900" : "bg-transparent",
                      )}
                    />

                    {/* Checkbox */}
                    <div className="pt-0.5 pl-1">
                      <Checkbox
                        checked={isSelected}
                        onCheckedChange={() => handleToggleTask(task.id)}
                        disabled={activeBatchAction !== null}
                        aria-label={
                          isSelected
                            ? `Desmarcar ${task.source_title}`
                            : `Selecionar ${task.source_title}`
                        }
                      />
                    </div>

                    {/* Content — links to task detail */}
                    <Link href={`/tasks/${task.id}`} className="flex-1 min-w-0">
                      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                        <div className="min-w-0">
                          <h3 className="truncate text-sm font-semibold text-stone-950 transition-colors group-hover:text-stone-600">
                            {task.source_title}
                          </h3>
                          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-stone-400">
                            <span className="uppercase tracking-wide font-medium text-stone-500">
                              {task.source_type}
                            </span>
                            <Separator orientation="vertical" className="h-3" />
                            <span className="flex items-center gap-1">
                              <Clock className="w-3 h-3" />
                              {formatDate(task.created_at)}
                            </span>
                            <Separator orientation="vertical" className="h-3" />
                            <span>
                              {task.clips_count} {task.clips_count === 1 ? "corte" : "cortes"}
                            </span>
                          </div>
                        </div>

                        <div className="flex-shrink-0">
                          {getStatusBadge(task.status)}
                        </div>
                      </div>
                    </Link>
                  </div>
                );
              })}
            </div>
          </>
        )}
      </div>

      {/* ── Floating batch command bar ────────────────────────── */}
      {selectedCount > 0 && (
        <div
          className="fixed inset-x-0 bottom-0 z-50 flex justify-center px-4 pb-5 pointer-events-none"
          style={{ animation: "command-bar-in 0.25s cubic-bezier(0.16, 1, 0.3, 1) both" }}
        >
          <div
            className="pointer-events-auto flex items-center gap-1 rounded-2xl border border-stone-800 bg-stone-950 px-2 py-2 shadow-2xl"
            style={{ animation: "command-bar-pulse 3s ease-in-out infinite" }}
          >
            {/* Select all checkbox */}
            <div className="flex items-center gap-2.5 pl-2 pr-3">
              <Checkbox
                checked={allVisibleSelected ? true : someSelected ? "indeterminate" : false}
                onCheckedChange={handleToggleAllVisible}
                disabled={activeBatchAction !== null}
                aria-label="Selecionar todas"
                className="border-stone-600 data-[state=checked]:bg-white data-[state=checked]:text-stone-950 data-[state=checked]:border-white data-[state=indeterminate]:bg-stone-500 data-[state=indeterminate]:border-stone-500"
              />
              <span className="text-sm font-medium text-white tabular-nums">
                {selectedCount}
                <span className="text-stone-400 ml-0.5">
                  {" "}selecionadas
                </span>
              </span>
            </div>

            <Separator orientation="vertical" className="h-6 bg-stone-700" />

            {/* Action buttons */}
            <div className="flex items-center gap-0.5 px-1">
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => void handleCancelSelected()}
                    disabled={cancelableCount === 0 || activeBatchAction !== null}
                    className="text-stone-300 hover:text-white hover:bg-stone-800 disabled:text-stone-600 disabled:hover:bg-transparent"
                  >
                    {activeBatchAction === "cancel" ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <PauseCircle className="w-4 h-4" />
                    )}
                    <span className="hidden sm:inline">Cancelar</span>
                    {cancelableCount > 0 && (
                      <span className="text-xs text-stone-500">{cancelableCount}</span>
                    )}
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="top" sideOffset={8}>
                  Cancelar {cancelableCount} {cancelableCount === 1 ? "geração ativa" : "gerações ativas"}
                </TooltipContent>
              </Tooltip>

              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => void handleResumeSelected()}
                    disabled={resumableCount === 0 || activeBatchAction !== null}
                    className="text-stone-300 hover:text-white hover:bg-stone-800 disabled:text-stone-600 disabled:hover:bg-transparent"
                  >
                    {activeBatchAction === "resume" ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <RotateCcw className="w-4 h-4" />
                    )}
                    <span className="hidden sm:inline">Retomar</span>
                    {resumableCount > 0 && (
                      <span className="text-xs text-stone-500">{resumableCount}</span>
                    )}
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="top" sideOffset={8}>
                  Retomar {resumableCount} {resumableCount === 1 ? "geração com erro/cancelada" : "gerações com erro/canceladas"}
                </TooltipContent>
              </Tooltip>

              <Separator orientation="vertical" className="h-6 bg-stone-700" />

              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setShowDeleteDialog(true)}
                    disabled={selectedCount === 0 || activeBatchAction !== null}
                    className="text-red-400 hover:text-red-300 hover:bg-red-950/50 disabled:text-stone-600 disabled:hover:bg-transparent"
                  >
                    {activeBatchAction === "delete" ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Trash2 className="w-4 h-4" />
                    )}
                    <span className="hidden sm:inline">Excluir</span>
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="top" sideOffset={8}>
                  Excluir {selectedCount} {selectedCount === 1 ? "geração" : "gerações"}
                </TooltipContent>
              </Tooltip>
            </div>

            <Separator orientation="vertical" className="h-6 bg-stone-700" />

            {/* Clear selection */}
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  onClick={() => {
                    setSelectedTaskIds([]);
                    setBatchNotice(null);
                  }}
                  disabled={activeBatchAction !== null}
                  className="text-stone-400 hover:text-white hover:bg-stone-800 rounded-xl"
                  aria-label="Limpar seleção"
                >
                  <X className="w-4 h-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="top" sideOffset={8}>
                Limpar seleção
              </TooltipContent>
            </Tooltip>
          </div>
        </div>
      )}

      {/* ── Delete confirmation dialog ────────────────────────── */}
      <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Excluir {selectedCount} {selectedCount === 1 ? "geração" : "gerações"}?</AlertDialogTitle>
            <AlertDialogDescription>
              Isso vai remover permanentemente {selectedCount === 1 ? "esta geração" : "estas gerações"} e todos os
              cortes associados. Não é possível desfazer.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={activeBatchAction === "delete"}>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => void handleDeleteSelected()}
              disabled={activeBatchAction === "delete" || selectedCount === 0}
              className="bg-red-600 hover:bg-red-700"
            >
              {activeBatchAction === "delete" ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Excluindo...
                </>
              ) : (
                "Excluir"
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
