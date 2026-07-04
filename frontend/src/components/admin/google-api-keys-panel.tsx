"use client";

import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, Loader2, Plus, ShieldCheck, Trash2, XCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type KeyHealth = {
  ok: boolean;
  detail?: string;
  checked_at?: string;
} | null;

type GoogleKeyEntry = {
  index: number;
  masked_key: string;
  source: "admin" | "environment";
  removable: boolean;
  health: KeyHealth;
};

type GoogleKeyPool = {
  keys: GoogleKeyEntry[];
  min_keys: number;
  max_keys: number;
  failover_enabled: boolean;
};

export function GoogleApiKeysPanel() {
  const [pool, setPool] = useState<GoogleKeyPool | null>(null);
  const [newKey, setNewKey] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [testingIndex, setTestingIndex] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const loadPool = useCallback(async () => {
    try {
      setIsLoading(true);
      const response = await fetch("/api/admin/google-api-keys", { cache: "no-store" });
      if (!response.ok) {
        setError("Não foi possível carregar as chaves de API.");
        return;
      }
      setPool((await response.json()) as GoogleKeyPool);
      setError(null);
    } catch {
      setError("Não foi possível conectar ao backend.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadPool();
  }, [loadPool]);

  async function addKey() {
    const key = newKey.trim();
    if (!key) return;
    setIsSaving(true);
    setError(null);
    setNotice(null);
    try {
      const response = await fetch("/api/admin/google-api-keys", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ api_key: key }),
      });
      const data = await response.json();
      if (!response.ok) {
        setError(traduzErro(data?.detail) ?? "Não foi possível adicionar a chave.");
        return;
      }
      setPool(data as GoogleKeyPool);
      setNewKey("");
      setNotice("Chave adicionada. Ela nunca será exibida por completo novamente.");
    } catch {
      setError("Falha de rede ao adicionar a chave.");
    } finally {
      setIsSaving(false);
    }
  }

  async function removeKey(index: number) {
    setIsSaving(true);
    setError(null);
    setNotice(null);
    try {
      const response = await fetch(`/api/admin/google-api-keys/${index}`, {
        method: "DELETE",
      });
      const data = await response.json();
      if (!response.ok) {
        setError(traduzErro(data?.detail) ?? "Não foi possível remover a chave.");
        return;
      }
      setPool(data as GoogleKeyPool);
      setNotice("Chave removida.");
    } catch {
      setError("Falha de rede ao remover a chave.");
    } finally {
      setIsSaving(false);
    }
  }

  async function testKey(index: number) {
    setTestingIndex(index);
    setError(null);
    setNotice(null);
    try {
      const response = await fetch("/api/admin/google-api-keys/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ index }),
      });
      const data = await response.json();
      if (!response.ok) {
        setError(traduzErro(data?.detail) ?? "Não foi possível testar a chave.");
        return;
      }
      setNotice(
        data.ok
          ? `Chave ${data.target} funcionando.`
          : `Chave ${data.target} falhou: ${data.detail ?? "erro desconhecido"}`,
      );
      await loadPool();
    } catch {
      setError("Falha de rede ao testar a chave.");
    } finally {
      setTestingIndex(null);
    }
  }

  const atMax = Boolean(pool && pool.keys.length >= pool.max_keys);

  return (
    <div className="space-y-4 px-5 py-5">
      <p className="text-sm text-stone-600">
        Cadastre de 1 a {pool?.max_keys ?? 5} chaves da API do Google (Gemini). Quando uma
        chave atingir o limite de uso ou falhar temporariamente, o sistema troca
        automaticamente para a próxima — a geração de cortes continua sem interrupção.
      </p>

      {isLoading ? (
        <div className="flex items-center gap-2 text-sm text-stone-500">
          <Loader2 className="h-4 w-4 animate-spin" /> Carregando chaves...
        </div>
      ) : (
        <ul className="space-y-2">
          {(pool?.keys ?? []).map((entry) => (
            <li
              key={`${entry.source}-${entry.index}`}
              className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-stone-200 bg-stone-50 px-3 py-2"
            >
              <div className="flex items-center gap-3">
                <code className="text-sm text-stone-800">{entry.masked_key}</code>
                <Badge variant="outline" className="text-xs">
                  {entry.source === "environment" ? "arquivo .env" : `chave ${entry.index + 1}`}
                </Badge>
                {entry.health ? (
                  entry.health.ok ? (
                    <Badge className="bg-emerald-100 text-emerald-700 hover:bg-emerald-100">
                      <CheckCircle2 className="mr-1 h-3 w-3" /> ativa
                    </Badge>
                  ) : (
                    <Badge className="bg-red-100 text-red-700 hover:bg-red-100">
                      <XCircle className="mr-1 h-3 w-3" /> com falha
                    </Badge>
                  )
                ) : (
                  <Badge variant="secondary" className="text-xs">
                    não testada
                  </Badge>
                )}
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={testingIndex !== null}
                  onClick={() => void testKey(entry.index)}
                >
                  {testingIndex === entry.index ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <ShieldCheck className="h-3.5 w-3.5" />
                  )}
                  Testar
                </Button>
                {entry.removable ? (
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={isSaving}
                    onClick={() => void removeKey(entry.index)}
                    className="text-red-600 hover:bg-red-50 hover:text-red-700"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                    Remover
                  </Button>
                ) : null}
              </div>
            </li>
          ))}
          {pool && pool.keys.length === 0 ? (
            <li className="rounded-md border border-dashed border-stone-300 px-3 py-4 text-sm text-stone-500">
              Nenhuma chave configurada ainda. Adicione pelo menos 1 chave para gerar cortes.
            </li>
          ) : null}
        </ul>
      )}

      <div className="flex gap-2">
        <Input
          type="password"
          placeholder="Cole aqui uma nova chave da API do Google (AIza...)"
          value={newKey}
          onChange={(event) => setNewKey(event.target.value)}
          disabled={atMax || isSaving}
        />
        <Button onClick={() => void addKey()} disabled={atMax || isSaving || !newKey.trim()}>
          {isSaving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
          Adicionar
        </Button>
      </div>
      {atMax ? (
        <p className="text-xs text-stone-500">
          Limite de {pool?.max_keys} chaves atingido. Remova uma chave para adicionar outra.
        </p>
      ) : null}

      {error ? <p className="text-sm text-red-700">{error}</p> : null}
      {notice ? <p className="text-sm text-emerald-700">{notice}</p> : null}
    </div>
  );
}

function traduzErro(detail: unknown): string | null {
  if (typeof detail !== "string" || !detail) return null;
  const traducoes: Record<string, string> = {
    "This API key is already registered": "Esta chave já está cadastrada.",
    "API key cannot be empty": "A chave não pode ficar vazia.",
    "At least 1 API key must remain configured":
      "É preciso manter pelo menos 1 chave configurada.",
    "The environment GOOGLE_API_KEY cannot be removed from here":
      "A chave definida no arquivo .env não pode ser removida por aqui.",
    "API key not found": "Chave não encontrada.",
    "Provide index or api_key to test": "Informe qual chave testar.",
  };
  if (detail.startsWith("Maximum of")) {
    return "Número máximo de chaves atingido.";
  }
  return traducoes[detail] ?? detail;
}
