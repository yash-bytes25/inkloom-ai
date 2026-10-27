import type {
  DiffChunkType,
  Finding,
  FindingResolutionStatus,
} from '../types/governance'

export interface InlineChunk {
  type: DiffChunkType
  text: string
}

/**
 * Validates that version selections are valid numbers and available within submission.
 */
export function validateVersionSelection(
  origVersion: number,
  newerVersion: number,
  availableVersions: number[]
): { valid: boolean; error?: string } {
  if (!availableVersions.includes(origVersion)) {
    return { valid: false, error: `Base version v${origVersion} is not available.` }
  }
  if (!availableVersions.includes(newerVersion)) {
    return { valid: false, error: `Target version v${newerVersion} is not available.` }
  }
  return { valid: true }
}

/**
 * Classifies a finding's resolution status based on origin and target finding lists.
 */
export function classifyFindingResolution(
  finding: Finding,
  isFromOriginal: boolean,
  counterpartFindings: Finding[]
): FindingResolutionStatus {
  const getRuleSig = (f: Finding) =>
    `${f.category}::${(f.rule_id || '').toLowerCase()}::${(f.rule_name_or_fact || '').toLowerCase()}`

  const targetSig = getRuleSig(finding)
  const isPresentInCounterpart = counterpartFindings.some(
    (cf) => getRuleSig(cf) === targetSig
  )

  if (isFromOriginal) {
    return isPresentInCounterpart ? 'unresolved' : 'resolved'
  } else {
    return isPresentInCounterpart ? 'unresolved' : 'introduced'
  }
}

/**
 * Calculates net finding delta between revisions.
 */
export function calculateFindingDelta(
  resolvedCount: number,
  _unresolvedCount: number,
  introducedCount: number
): { netChange: number; isImprovement: boolean } {
  const netChange = introducedCount - resolvedCount
  return {
    netChange,
    isImprovement: resolvedCount > introducedCount,
  }
}
