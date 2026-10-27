import test, { describe } from 'node:test'
import assert from 'node:assert'
import {
  validateVersionSelection,
  classifyFindingResolution,
  calculateFindingDelta,
} from './diffHelpers.ts'
import type { Finding } from '../types/governance.ts'

describe('Diff and Versioning Helper Logic', () => {
  test('validateVersionSelection checks validity against available versions', () => {
    const available = [1, 2, 3]

    assert.strictEqual(validateVersionSelection(1, 2, available).valid, true)
    assert.strictEqual(validateVersionSelection(2, 3, available).valid, true)

    const invalidOrig = validateVersionSelection(0, 2, available)
    assert.strictEqual(invalidOrig.valid, false)
    assert.match(invalidOrig.error || '', /Base version v0 is not available/)

    const invalidNewer = validateVersionSelection(1, 5, available)
    assert.strictEqual(invalidNewer.valid, false)
    assert.match(invalidNewer.error || '', /Target version v5 is not available/)
  })

  test('classifyFindingResolution identifies resolved findings', () => {
    const findingOrig: Finding = {
      id: 'f-cheap',
      category: 'prohibited_terminology',
      severity: 'critical',
      matched_text: 'cheap',
      start_index: 0,
      end_index: 5,
      explanation: 'Use accessible luxury',
      rule_id: 'p-cheap',
      rule_name_or_fact: 'Prohibited term "cheap"',
      suggested_correction: 'accessible luxury',
      evidence_status: 'confirmed_violation',
    }

    // In newer, 'p-cheap' is absent
    const counterpart: Finding[] = []
    const status = classifyFindingResolution(findingOrig, true, counterpart)
    assert.strictEqual(status, 'resolved')
  })

  test('classifyFindingResolution identifies unresolved findings when rule is still present', () => {
    const findingOrig: Finding = {
      id: 'f-unbreakable',
      category: 'prohibited_terminology',
      severity: 'critical',
      matched_text: 'unbreakable',
      start_index: 10,
      end_index: 21,
      explanation: 'Absolute durability claims',
      rule_id: 'p-unbr',
      rule_name_or_fact: 'Prohibited term "unbreakable"',
      suggested_correction: 'durable',
      evidence_status: 'confirmed_violation',
    }

    const counterpart: Finding[] = [findingOrig]
    const status = classifyFindingResolution(findingOrig, true, counterpart)
    assert.strictEqual(status, 'unresolved')
  })

  test('classifyFindingResolution identifies introduced findings', () => {
    const newFinding: Finding = {
      id: 'f-intro',
      category: 'required_disclaimer',
      severity: 'warning',
      matched_text: '30-hour battery',
      start_index: 0,
      end_index: 15,
      explanation: 'Requires battery disclaimer',
      rule_id: 'd-batt',
      rule_name_or_fact: 'Battery Claims',
      suggested_correction: 'Add disclaimer',
      evidence_status: 'potential_issue',
    }

    const origFindings: Finding[] = []
    const status = classifyFindingResolution(newFinding, false, origFindings)
    assert.strictEqual(status, 'introduced')
  })

  test('calculateFindingDelta computes correct net delta and improvement boolean', () => {
    // 3 resolved, 0 introduced -> improvement
    const d1 = calculateFindingDelta(3, 1, 0)
    assert.strictEqual(d1.netChange, -3)
    assert.strictEqual(d1.isImprovement, true)

    // 1 resolved, 2 introduced -> regression
    const d2 = calculateFindingDelta(1, 1, 2)
    assert.strictEqual(d2.netChange, 1)
    assert.strictEqual(d2.isImprovement, false)
  })
})
