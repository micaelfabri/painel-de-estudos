import { Globe } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { SettingsResponse } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { GithubIcon, LinkedinIcon } from "./BrandIcons";

// Só links https vão para href (os mesmos validados no backend)
const safe = (v: unknown) => (typeof v === "string" && v.startsWith("https://") ? v : null);

// Ícone na cor da marca; no hover o botão inteiro assume a cor da marca
const GITHUB =
  "group text-foreground hover:border-[var(--brand-github)] hover:bg-[var(--brand-github)] hover:text-[var(--brand-github-foreground)]";
const LINKEDIN =
  "group text-foreground hover:border-[var(--brand-linkedin)] hover:bg-[var(--brand-linkedin)] hover:text-[var(--brand-linkedin-foreground)]";

/** Rodapé (SPEC D21): autoria e links; o site aparece como "em breve" até ter endereço */
export function AppFooter() {
  const settings = useApi<SettingsResponse>("/settings");
  const values = settings.data?.values ?? {};
  const github = safe(values.github_url);
  const linkedin = safe(values.linkedin_url);
  const site = safe(values.site_url);
  const year = new Date().getFullYear();

  return (
    <footer role="contentinfo" className="mt-auto border-t border-border bg-muted px-6 py-6">
      <div className="mx-auto flex w-full max-w-[1280px] flex-wrap items-center justify-between gap-4">
        <div className="space-y-1">
          <p className="text-sm text-muted-foreground">© {year} Painel de Estudos.</p>
          <p className="text-xs text-muted-foreground">Roda só neste PC · dados em ./data</p>
        </div>
        <ul className="flex flex-wrap gap-2" aria-label="Links do autor">
          {github && (
            <li>
              <Button asChild variant="outline" size="sm" className={GITHUB}>
                <a href={github} target="_blank" rel="noopener noreferrer">
                  <GithubIcon className="text-[var(--brand-github)] transition-colors group-hover:text-current" />
                  GitHub
                </a>
              </Button>
            </li>
          )}
          {linkedin && (
            <li>
              <Button asChild variant="outline" size="sm" className={LINKEDIN}>
                <a href={linkedin} target="_blank" rel="noopener noreferrer">
                  <LinkedinIcon className="text-[var(--brand-linkedin)] transition-colors group-hover:text-current" />
                  LinkedIn
                </a>
              </Button>
            </li>
          )}
          <li>
            {site ? (
              <Button asChild variant="outline" size="sm">
                <a href={site} target="_blank" rel="noopener noreferrer">
                  <Globe aria-hidden="true" />
                  Site
                </a>
              </Button>
            ) : (
              <Button variant="outline" size="sm" disabled aria-disabled="true">
                <Globe aria-hidden="true" />
                Site (em breve)
              </Button>
            )}
          </li>
        </ul>
      </div>
    </footer>
  );
}
