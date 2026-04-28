"use client";

import { Container, Title, Text, Stack, List, Alert } from "@mantine/core";

export default function AboutPage() {
  return (
    <Container size="sm" py="xl">
      <Stack gap="xl">
        <div>
          <Text
            style={{
              fontFamily: "'Public Sans', Arial, sans-serif",
              fontSize: 11,
              textTransform: "uppercase",
              letterSpacing: "0.1em",
              color: "var(--nsw-grey-04)",
              marginBottom: 8,
            }}
          >
            About
          </Text>
          <Title order={1} style={{ fontSize: 36, lineHeight: 1.15 }}>
            Nimby Agent
          </Title>
          <div
            style={{
              width: 60,
              height: 3,
              background: "var(--nsw-brand-dark)",
              margin: "12px 0",
            }}
          />
        </div>

        <Text style={{ lineHeight: 1.75, color: "var(--nsw-text)", fontSize: 15 }}>
          Nimby Agent helps NSW residents understand planning proposals on
          exhibition in their area. It reads the actual proposal documents,
          extracts key information, and presents it in plain language with
          citations you can verify.
        </Text>

        <div
          style={{
            borderTop: "2px solid var(--nsw-brand-dark)",
            paddingTop: 20,
          }}
        >
          <Text
            style={{
              fontFamily: "'Public Sans', Arial, sans-serif",
              fontSize: 10,
              textTransform: "uppercase",
              letterSpacing: "0.08em",
              color: "var(--nsw-grey-04)",
              marginBottom: 12,
            }}
          >
            How it works
          </Text>
          <List
            spacing="sm"
            style={{ color: "var(--nsw-text)", fontSize: 14, lineHeight: 1.6 }}
          >
            <List.Item>
              <strong>Search</strong> &mdash; Enter your address to find
              proposals near you.
            </List.Item>
            <List.Item>
              <strong>Read</strong> &mdash; Each proposal has a plain-language
              brief citing source documents.
            </List.Item>
            <List.Item>
              <strong>Ask</strong> &mdash; Ask questions and get answers
              grounded in the actual documents.
            </List.Item>
            <List.Item>
              <strong>Respond</strong> &mdash; Draft an evidence-based
              submission backed by the proposal&apos;s own studies.
            </List.Item>
          </List>
        </div>

        <div
          style={{
            borderTop: "2px solid var(--nsw-brand-dark)",
            paddingTop: 20,
          }}
        >
          <Text
            style={{
              fontFamily: "'Public Sans', Arial, sans-serif",
              fontSize: 10,
              textTransform: "uppercase",
              letterSpacing: "0.08em",
              color: "var(--nsw-grey-04)",
              marginBottom: 12,
            }}
          >
            Data Sources
          </Text>
          <List
            spacing="sm"
            style={{ color: "var(--nsw-text)", fontSize: 14, lineHeight: 1.6 }}
          >
            <List.Item>
              All data from the NSW Planning Portal
              (planningportal.nsw.gov.au)
            </List.Item>
            <List.Item>
              Documents are the actual PDFs published during exhibition
            </List.Item>
            <List.Item>
              Every factual claim cites a specific document and page
            </List.Item>
          </List>
        </div>

        <Alert color="yellow" title="Limitations">
          <List spacing="xs" size="sm">
            <List.Item>
              Information only, not legal or planning advice.
            </List.Item>
            <List.Item>
              AI-generated summaries may contain errors. Verify against source
              documents.
            </List.Item>
            <List.Item>
              Some scanned PDFs may not have been fully extracted.
            </List.Item>
            <List.Item>
              Exhibition dates may change. Check the official portal.
            </List.Item>
          </List>
        </Alert>
      </Stack>
    </Container>
  );
}
