"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowLeft, CheckCircle, KeyRound, Palette, Settings, Sparkles, Type } from "lucide-react";

import { GoogleApiKeysPanel } from "@/components/admin/google-api-keys-panel";
import {
  RuntimeSettingsForm,
  type RuntimeSetting,
} from "@/components/admin/runtime-settings-form";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Slider } from "@/components/ui/slider";
import { track } from "@/lib/datafast";

interface FontOption {
  name: string;
  display_name: string;
  format?: string;
}

type Preferences = {
  fontFamily: string;
  fontSize: number;
  fontColor: string;
};

const DEFAULT_PREFERENCES: Preferences = {
  fontFamily: "THEBOLDFONT",
  fontSize: 32,
  fontColor: "#FFFFFF",
};

export default function SettingsPage() {
  const [preferences, setPreferences] = useState<Preferences>(DEFAULT_PREFERENCES);
  const [availableFonts, setAvailableFonts] = useState<FontOption[]>([]);
  const [runtimeSettings, setRuntimeSettings] = useState<RuntimeSetting[]>([]);
  const [runtimeError, setRuntimeError] = useState<string | null>(null);
  const [isLoadingRuntime, setIsLoadingRuntime] = useState(true);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const raw = window.localStorage.getItem("supoclip.preferences");
    if (raw) {
      try {
        setPreferences({ ...DEFAULT_PREFERENCES, ...JSON.parse(raw) });
      } catch {
        window.localStorage.removeItem("supoclip.preferences");
      }
    }

    async function loadFonts() {
      try {
        const response = await fetch("/api/fonts", { cache: "no-store" });
        if (!response.ok) return;
        const data = await response.json();
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
      } catch (error) {
        console.error("Falha ao carregar fontes:", error);
      }
    }

    async function loadRuntimeSettings() {
      try {
        setIsLoadingRuntime(true);
        const response = await fetch("/api/admin/runtime-settings", { cache: "no-store" });
        if (!response.ok) {
          setRuntimeError("Não foi possível carregar as configurações.");
          return;
        }
        const data = await response.json();
        setRuntimeSettings(data.settings || []);
      } catch {
        setRuntimeError("Não foi possível conectar à API de configurações do backend.");
      } finally {
        setIsLoadingRuntime(false);
      }
    }

    void loadFonts();
    void loadRuntimeSettings();
  }, []);

  function updatePreference<K extends keyof Preferences>(key: K, value: Preferences[K]) {
    setPreferences((current) => ({ ...current, [key]: value }));
    setSaved(false);
  }

  function savePreferences() {
    window.localStorage.setItem("supoclip.preferences", JSON.stringify(preferences));
    track("preferences_saved");
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  }

  return (
    <main className="min-h-screen bg-stone-50">
      <header className="border-b border-stone-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4">
          <Link href="/">
            <Button variant="ghost" size="sm">
              <ArrowLeft className="h-4 w-4" />
              Voltar
            </Button>
          </Link>
          <Link href="/list">
            <Button variant="outline" size="sm">Meus cortes</Button>
          </Link>
        </div>
      </header>

      <div className="mx-auto max-w-6xl space-y-6 px-4 py-8">
        <div>
          <div className="flex items-center gap-2">
            <Settings className="h-6 w-6 text-stone-950" />
            <h1 className="font-[var(--font-syne)] text-3xl font-bold text-stone-950">Configurações</h1>
          </div>
          <p className="mt-2 max-w-2xl text-sm text-stone-600">
            Defina os padrões locais e as chaves dos provedores desta instalação do SupoClip.
          </p>
        </div>

        <section className="rounded-lg border border-stone-200 bg-white">
          <div className="border-b border-stone-200 px-5 py-4">
            <div className="flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-stone-950" />
              <h2 className="text-lg font-semibold text-stone-950">Chaves da API Google (IA)</h2>
            </div>
            <p className="mt-1 text-sm text-stone-600">
              Sistema de revezamento automático: se uma chave atingir o limite, a próxima assume.
              As chaves são salvas criptografadas no backend e nunca voltam a ser exibidas.
            </p>
          </div>
          <GoogleApiKeysPanel />
        </section>

        <Card className="border-stone-200">
          <CardContent className="p-5">
            <div className="mb-5">
              <h2 className="text-lg font-semibold text-stone-950">Legendas padrão</h2>
              <p className="mt-1 text-sm text-stone-600">
                Salvas neste navegador e aplicadas às novas gerações de cortes.
              </p>
            </div>

            <div className="grid gap-6 lg:grid-cols-[1fr_280px]">
              <div className="space-y-5">
                <div className="space-y-2">
                  <Label className="flex items-center gap-2">
                    <Type className="h-4 w-4" />
                    Fonte
                  </Label>
                  <Select
                    value={preferences.fontFamily}
                    onValueChange={(value) => updatePreference("fontFamily", value)}
                  >
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
                  <Label>Tamanho da fonte: {preferences.fontSize}px</Label>
                  <Slider
                    value={[preferences.fontSize]}
                    min={12}
                    max={72}
                    step={2}
                    onValueChange={(value) => updatePreference("fontSize", value[0])}
                  />
                </div>

                <div className="space-y-2">
                  <Label className="flex items-center gap-2">
                    <Palette className="h-4 w-4" />
                    Cor da fonte
                  </Label>
                  <div className="flex gap-2">
                    <Input
                      value={preferences.fontColor}
                      onChange={(event) => updatePreference("fontColor", event.target.value)}
                      pattern="^#[0-9A-Fa-f]{6}$"
                    />
                    <input
                      aria-label="Cor da fonte"
                      type="color"
                      value={preferences.fontColor}
                      onChange={(event) => updatePreference("fontColor", event.target.value)}
                      className="h-10 w-12 rounded-md border border-stone-300 bg-white"
                    />
                  </div>
                </div>

                {saved ? (
                  <Alert className="border-emerald-200 bg-emerald-50">
                    <CheckCircle className="h-4 w-4 text-emerald-600" />
                    <AlertDescription className="text-sm text-emerald-700">
                      Preferências salvas.
                    </AlertDescription>
                  </Alert>
                ) : null}

                <Button onClick={savePreferences}>Salvar legendas padrão</Button>
              </div>

              <div className="flex aspect-[9/16] items-center justify-center rounded-md bg-stone-950 p-4">
                <p
                  className="text-center font-bold leading-tight"
                  style={{
                    color: preferences.fontColor,
                    fontFamily: `'${preferences.fontFamily}', system-ui, sans-serif`,
                    fontSize: `${Math.min(Math.max(preferences.fontSize, 12), 40)}px`,
                    textShadow: "0 2px 8px rgba(0,0,0,0.8)",
                  }}
                >
                  Sua legenda vai ficar assim
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        <section className="rounded-lg border border-stone-200 bg-white">
          <div className="border-b border-stone-200 px-5 py-4">
            <div className="flex items-center gap-2">
              <KeyRound className="h-5 w-5 text-stone-950" />
              <h2 className="text-lg font-semibold text-stone-950">Outras chaves e provedores</h2>
            </div>
            <p className="mt-1 text-sm text-stone-600">
              Valores salvos valem para toda esta instalação local. Não exponha esta página na internet.
            </p>
          </div>

          {isLoadingRuntime ? (
            <div className="px-5 py-6 text-sm text-stone-500">Carregando configurações...</div>
          ) : runtimeError ? (
            <div className="px-5 py-6 text-sm text-red-700">{runtimeError}</div>
          ) : (
            <RuntimeSettingsForm settings={runtimeSettings} />
          )}
        </section>

        <Separator />

        <p className="text-xs text-stone-500">
          Contas, cobrança e preferências por usuário foram removidas no modo local.
        </p>
      </div>
    </main>
  );
}
