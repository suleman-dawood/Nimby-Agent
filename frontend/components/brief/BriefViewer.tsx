"use client";

import {
  Tabs,
  Paper,
  Text,
  Group,
  Button,
  Stack,
} from "@mantine/core";
import { useState } from "react";

const CITE_PATTERN = /\[doc:\s*(.+?)\s*\|\s*p\.?\s*(\d+)\]/g;

interface Props {
  markdown: string;
  onCitationClick: (docTitle: string, page: number) => void;
}

interface Section {
  heading: string;
  body: string;
  citations: { docTitle: string; page: number; key: string }[];
}

function parseSections(markdown: string): {
  header: string;
  sections: Section[];
  references: string;
} {
  const parts = markdown.split(/^(## .+)$/m);
  let header = "";
  const sections: Section[] = [];
  let references = "";

  for (let i = 0; i < parts.length; i++) {
    const part = parts[i].trim();
    if (!part) continue;

    if (part.startsWith("## References")) {
      references = parts[i + 1] || "";
      i++;
      continue;
    }

    if (part.startsWith("## ")) {
      const body = parts[i + 1] || "";
      const citations: Section["citations"] = [];
      const seen = new Set<string>();

      let match;
      const re = new RegExp(CITE_PATTERN.source, "g");
      while ((match = re.exec(body)) !== null) {
        const key = `${match[1]}|${match[2]}`;
        if (!seen.has(key)) {
          seen.add(key);
          citations.push({
            docTitle: match[1].trim(),
            page: parseInt(match[2]),
            key,
          });
        }
      }

      sections.push({
        heading: part.replace("## ", ""),
        body: body.replace(CITE_PATTERN, "").replace(/\s{2,}/g, " "),
        citations,
      });
      i++;
      continue;
    }

    if (!sections.length) {
      header += part + "\n";
    }
  }

  return { header, sections, references };
}

function markdownToHtml(md: string): string {
  return md
    .replace(/^# (.+)$/gm, '<h1 style="font-family: DM Serif Display, serif; font-size: 24px; margin-bottom: 8px;">$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\n\n/g, '<br /><br />')
    .replace(/\n/g, "<br />");
}

export default function BriefViewer({ markdown, onCitationClick }: Props) {
  const { header, sections, references } = parseSections(markdown);
  const [activeTab, setActiveTab] = useState<string | null>(
    sections[0]?.heading || null
  );

  return (
    <Stack gap="md">
      {header && (
        <div
          style={{
            paddingBottom: 12,
            borderBottom: "1px solid var(--rule)",
          }}
          dangerouslySetInnerHTML={{ __html: markdownToHtml(header) }}
        />
      )}

      {sections.length > 0 && (
        <Tabs value={activeTab} onChange={setActiveTab}>
          <Tabs.List>
            {sections.map((s) => (
              <Tabs.Tab key={s.heading} value={s.heading}>
                {s.heading}
              </Tabs.Tab>
            ))}
          </Tabs.List>

          {sections.map((s) => (
            <Tabs.Panel key={s.heading} value={s.heading} pt="md">
              <Text
                size="sm"
                style={{
                  lineHeight: 1.75,
                  color: "var(--ink)",
                  maxWidth: 640,
                }}
              >
                {s.body}
              </Text>

              {s.citations.length > 0 && (
                <div
                  style={{
                    marginTop: 16,
                    paddingTop: 12,
                    borderTop: "1px solid var(--rule)",
                  }}
                >
                  <Text
                    style={{
                      fontFamily: "'IBM Plex Mono', monospace",
                      fontSize: 10,
                      textTransform: "uppercase",
                      letterSpacing: "0.08em",
                      color: "var(--ink-faint)",
                      marginBottom: 8,
                    }}
                  >
                    Sources
                  </Text>
                  <Group gap="xs" wrap="wrap">
                    {s.citations.map((c) => (
                      <Button
                        key={c.key}
                        size="xs"
                        variant="light"
                        onClick={() => onCitationClick(c.docTitle, c.page)}
                      >
                        {c.docTitle.length > 30
                          ? c.docTitle.slice(0, 28) + "\u2026"
                          : c.docTitle}{" "}
                        p.{c.page}
                      </Button>
                    ))}
                  </Group>
                </div>
              )}
            </Tabs.Panel>
          ))}
        </Tabs>
      )}

      {references && (
        <div
          style={{
            padding: 16,
            background: "var(--paper-warm)",
            border: "1px solid var(--rule)",
          }}
        >
          <Text
            style={{
              fontFamily: "'IBM Plex Mono', monospace",
              fontSize: 10,
              textTransform: "uppercase",
              letterSpacing: "0.08em",
              color: "var(--ink-faint)",
              marginBottom: 8,
            }}
          >
            References
          </Text>
          <Text
            size="xs"
            style={{
              whiteSpace: "pre-wrap",
              color: "var(--ink-light)",
              fontFamily: "'IBM Plex Sans', sans-serif",
              lineHeight: 1.6,
            }}
          >
            {references}
          </Text>
        </div>
      )}
    </Stack>
  );
}
