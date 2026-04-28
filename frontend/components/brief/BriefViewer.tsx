"use client";

import {
  Tabs,
  Group,
  Button,
  Stack,
  Text,
} from "@mantine/core";
import { useState } from "react";
import ReactMarkdown from "react-markdown";

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
} {
  const parts = markdown.split(/^(## .+)$/m);
  let header = "";
  const sections: Section[] = [];

  for (let i = 0; i < parts.length; i++) {
    const part = parts[i].trim();
    if (!part) continue;

    if (part.startsWith("## References")) {
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

      // Clean up body for proper markdown rendering
      let cleanBody = body.replace(CITE_PATTERN, "");
      // Fix inline bullets: "text * bullet" → "text\n* bullet"
      cleanBody = cleanBody.replace(/([.!?])\s*\*\s+/g, "$1\n\n* ");
      // Fix inline numbered lists
      cleanBody = cleanBody.replace(/([.!?])\s*(\d+\.)\s+/g, "$1\n\n$2 ");

      sections.push({
        heading: part.replace("## ", ""),
        body: cleanBody,
        citations,
      });
      i++;
      continue;
    }

    if (!sections.length) {
      header += part + "\n";
    }
  }

  return { header, sections };
}

export default function BriefViewer({ markdown, onCitationClick }: Props) {
  const cleanMarkdown = markdown
    .replace(/\n---\n\*Citations resolved[\s\S]*$/, "")
    .replace(/\n---\n\*Facts verified[\s\S]*$/, "");
  const { header, sections } = parseSections(cleanMarkdown);
  const [activeTab, setActiveTab] = useState<string | null>(
    sections[0]?.heading || null
  );

  return (
    <Stack gap="md">
      {header && (
        <div
          className="brief-content"
          style={{
            paddingBottom: 12,
            borderBottom: "1px solid var(--nsw-grey-02)",
          }}
        >
          <ReactMarkdown>{header.replace(CITE_PATTERN, "")}</ReactMarkdown>
        </div>
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
              <div className="brief-content" style={{ maxWidth: 660 }}>
                <ReactMarkdown>{s.body}</ReactMarkdown>
              </div>

              {s.citations.length > 0 && (
                <div
                  style={{
                    marginTop: 16,
                    paddingTop: 12,
                    borderTop: "1px solid var(--nsw-grey-02)",
                  }}
                >
                  <Text
                    style={{
                      fontFamily: "'Public Sans', Arial, sans-serif",
                      fontSize: 11,
                      fontWeight: 600,
                      textTransform: "uppercase",
                      letterSpacing: "0.04em",
                      color: "var(--nsw-grey-04)",
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

      <style>{`
        .brief-content {
          font-family: 'Public Sans', Arial, sans-serif;
          font-size: 15px;
          line-height: 1.75;
          color: var(--nsw-text);
        }
        .brief-content h1 {
          font-size: 24px;
          font-weight: 700;
          color: var(--nsw-brand-dark);
          margin-bottom: 8px;
        }
        .brief-content h2 {
          font-size: 20px;
          font-weight: 700;
          color: var(--nsw-brand-dark);
          margin: 16px 0 8px;
        }
        .brief-content h3 {
          font-size: 17px;
          font-weight: 700;
          color: var(--nsw-brand-dark);
          margin: 12px 0 6px;
        }
        .brief-content p {
          margin: 0 0 12px;
        }
        .brief-content p:last-child {
          margin-bottom: 0;
        }
        .brief-content ul, .brief-content ol {
          margin: 8px 0 12px;
          padding-left: 24px;
        }
        .brief-content li {
          margin-bottom: 4px;
        }
        .brief-content strong {
          font-weight: 600;
        }
        .brief-content blockquote {
          border-left: 3px solid var(--nsw-brand-dark);
          padding-left: 16px;
          margin: 12px 0;
          color: var(--nsw-text-light);
        }
      `}</style>
    </Stack>
  );
}
