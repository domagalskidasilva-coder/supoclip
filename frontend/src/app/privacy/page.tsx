import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { HOSTED_APP_URL, getSiteUrl } from "@/lib/blog-posts";

const LAST_UPDATED = "June 25, 2026";
const CONTACT_EMAIL = "privacy@supoclip.com";

export const metadata: Metadata = {
  title: "Privacy Policy | SupoClip",
  description:
    "How SupoClip collects, uses, shares, and protects your data when you use the SupoClip video-clipping service.",
  alternates: {
    canonical: `${getSiteUrl()}/privacy`,
  },
  openGraph: {
    title: "SupoClip Privacy Policy",
    description: "How SupoClip handles your data.",
    type: "website",
    url: `${getSiteUrl()}/privacy`,
    siteName: "SupoClip",
  },
};

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3">
      <h2
        className="text-2xl font-bold tracking-tight"
        style={{ fontFamily: "var(--font-syne), var(--font-geist-sans), system-ui" }}
      >
        {title}
      </h2>
      <div className="space-y-3 text-base leading-7 text-muted-foreground">{children}</div>
    </section>
  );
}

export default function PrivacyPolicyPage() {
  return (
    <main className="min-h-screen bg-background text-foreground">
      <header className="border-b bg-background/95">
        <div className="mx-auto flex h-16 max-w-3xl items-center justify-between px-6">
          <Link href="/" className="flex items-center gap-2.5">
            <Image src="/logo.png" alt="SupoClip" width={24} height={24} className="rounded-lg" />
            <span
              className="text-lg font-bold tracking-tight"
              style={{ fontFamily: "var(--font-syne), var(--font-geist-sans), system-ui" }}
            >
              SupoClip
            </span>
          </Link>
          <a href={HOSTED_APP_URL} target="_blank" rel="noopener noreferrer">
            <Button variant="ghost" size="sm" className="hidden sm:inline-flex">
              Hosted App
              <ExternalLink className="h-3.5 w-3.5" />
            </Button>
          </a>
        </div>
      </header>

      <article className="mx-auto max-w-3xl px-6 py-14 md:py-20">
        <div className="space-y-3">
          <h1
            className="text-4xl font-extrabold tracking-tight sm:text-5xl"
            style={{ fontFamily: "var(--font-syne), var(--font-geist-sans), system-ui" }}
          >
            Privacy Policy
          </h1>
          <p className="text-sm text-muted-foreground">Last updated: {LAST_UPDATED}</p>
        </div>

        <div className="mt-12 space-y-10">
          <Section title="Overview">
            <p>
              This Privacy Policy explains how SupoClip (&ldquo;SupoClip,&rdquo; &ldquo;we,&rdquo;
              &ldquo;us&rdquo;) collects, uses, shares, and protects information when you use the
              SupoClip apps and hosted service (the &ldquo;Service&rdquo;), which turn long-form
              videos into short, captioned clips.
            </p>
            <p>
              This local build does not include account login, API keys, paid plans, or hosted
              billing. If you connect external providers for transcription, LLM processing, storage,
              or feedback, their own terms and privacy policies also apply.
            </p>
          </Section>

          <Section title="Information We Collect">
            <p className="font-medium text-foreground">Content you provide.</p>
            <p>
              To generate clips, we process the video URLs you submit (for example links to videos
              you are authorized to use) and any video files you upload. We store the resulting
              clips, transcripts, captions, and related processing metadata so you can view, edit,
              and export them. You are responsible for having the rights to any content you submit.
            </p>
            <p className="font-medium text-foreground">Usage, device, and log data.</p>
            <p>
              The local app may write technical logs, task metadata, generated files, and runtime
              settings to your configured database and filesystem. Browser preferences are stored in
              localStorage on the device where you run the frontend.
            </p>
          </Section>

          <Section title="How We Use Your Information">
            <ul className="list-disc space-y-2 pl-6">
              <li>Provide the Service&mdash;process your videos and generate, edit, and export clips.</li>
              <li>Maintain, debug, secure, and improve the Service.</li>
              <li>Store local preferences and runtime settings for the app instance.</li>
              <li>Comply with legal obligations and enforce our terms.</li>
            </ul>
          </Section>

          <Section title="Service Providers &amp; Subprocessors">
            <p>
              We share data with vendors that process it on our behalf, only as needed to provide
              the Service:
            </p>
            <ul className="list-disc space-y-2 pl-6">
              <li><span className="text-foreground">Transcription</span> &mdash; to transcribe audio from your videos.</li>
              <li><span className="text-foreground">AI/LLM providers</span> &mdash; to analyze transcripts and identify clip-worthy segments.</li>
              <li><span className="text-foreground">Local infrastructure</span> &mdash; your database, Redis instance, and filesystem.</li>
              <li><span className="text-foreground">Optional feedback integrations</span> &mdash; only if configured by the operator.</li>
            </ul>
            <p>
              We do not sell your personal information, and we do not use it for cross-context
              behavioral advertising. We may disclose information if required by law or to protect
              the rights, safety, and security of our users and the Service.
            </p>
          </Section>

          <Section title="Data Retention">
            <p>
              Tasks, uploaded videos, generated clips, transcripts, and runtime settings remain in
              your local database and filesystem until you delete them or reset the instance.
              Temporary processing files may be removed automatically after processing.
            </p>
          </Section>

          <Section title="Your Rights &amp; Choices">
            <p>
              You can delete individual tasks and clips from the app. Because this local build has
              no accounts, deleting the local database and generated media directories is the way to
              fully reset instance data. Questions can be sent to{" "}
              <a className="text-foreground underline" href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>.
            </p>
            <p>
              Depending on where you live (for example under GDPR or CCPA/CPRA), you may have rights
              to access, correct, delete, or port your personal data, and to object to or restrict
              certain processing. To exercise these rights, contact us at the address below. We will
              not discriminate against you for exercising your rights.
            </p>
          </Section>

          <Section title="Security">
            <p>
              Use HTTPS when exposing the app beyond your own machine, keep provider API keys out of
              source control, and restrict database, Redis, and media-file access to trusted users.
              No method of transmission or storage is completely secure, but these controls reduce
              the risk of accidental exposure.
            </p>
          </Section>

          <Section title="International Transfers">
            <p>
              External AI, transcription, storage, or feedback providers may process information in
              countries other than where you live. Review those providers before enabling them.
            </p>
          </Section>

          <Section title="Children&rsquo;s Privacy">
            <p>
              The Service is not directed to children under 13 (or the minimum age required in your
              jurisdiction), and we do not knowingly collect personal information from them. If you
              believe a child has provided us personal information, contact us and we will delete it.
            </p>
          </Section>

          <Section title="Changes to This Policy">
            <p>
              We may update this Privacy Policy from time to time. When we do, we will revise the
              &ldquo;Last updated&rdquo; date above and, where appropriate, provide additional
              notice. Your continued use of the Service after an update means you accept the revised
              policy.
            </p>
          </Section>

          <Section title="Contact Us">
            <p>
              Questions about this policy or your data? Email us at{" "}
              <a className="text-foreground underline" href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>.
            </p>
          </Section>
        </div>

        <div className="mt-14 border-t pt-8 text-sm text-muted-foreground">
          <Link href="/" className="underline hover:text-foreground">
            Back to SupoClip
          </Link>
        </div>
      </article>
    </main>
  );
}
