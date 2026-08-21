import type { QcFinding } from "../../api/contracts";

const QUOTED_TEXT = /[“"「『']([^”"」』']{2,64})[”"」』']/g;
const EDGE_QUOTES = /^[“”"「」『』'`]+|[“”"「」『』'`]+$/g;

function cleanKeyword(value: string) {
  return value.trim().replace(EDGE_QUOTES, "").trim();
}

export function findingKeywords(finding: QcFinding): string[] {
  const quoted = [finding.message, finding.suggestion, finding.evidence]
    .flatMap((source) => Array.from((source ?? "").matchAll(QUOTED_TEXT), (match) => cleanKeyword(match[1])));
  const evidence = cleanKeyword(finding.evidence ?? "");
  const candidates = quoted.length > 0
    ? quoted
    : evidence.includes("、") ? evidence.split("、").map(cleanKeyword) : [evidence];

  const unique = Array.from(new Set(candidates.filter((keyword) => keyword.length >= 2)));
  return unique
    .filter((keyword) => !unique.some((other) => other !== keyword && keyword.includes(other)))
    .slice(0, 4);
}

export function locateCandidates(finding: QcFinding): string[] {
  const evidence = cleanKeyword(finding.evidence ?? "");
  return Array.from(new Set([...findingKeywords(finding), evidence].filter(Boolean)));
}
