import test, { describe } from 'node:test'
import assert from 'node:assert'
import {
  validateBrandProfile,
  validateProhibitedTerm,
  validatePreferredWording,
  validateApprovedFact,
  validateRequiredDisclaimer,
  validateFullBrandRules,
} from './guidelinesValidation.ts'
import type { BrandRulesConfig } from '../types/governance.ts'

describe('Brand Guidelines Validation Logic', () => {
  test('validateBrandProfile rejects blank names and accepts valid names', () => {
    assert.strictEqual(validateBrandProfile('').valid, false)
    assert.strictEqual(validateBrandProfile('   ').valid, false)
    assert.strictEqual(validateBrandProfile('NovaSound Audio').valid, true)
  })

  test('validateProhibitedTerm rejects empty term or explanation', () => {
    const emptyTerm = validateProhibitedTerm({ term_or_pattern: '', explanation: 'Some reason' })
    assert.strictEqual(emptyTerm.valid, false)

    const emptyExp = validateProhibitedTerm({ term_or_pattern: 'cheap', explanation: '' })
    assert.strictEqual(emptyExp.valid, false)

    const validTerm = validateProhibitedTerm({
      term_or_pattern: 'cheap',
      explanation: 'Use affordable instead',
      is_regex: false,
    })
    assert.strictEqual(validTerm.valid, true)
  })

  test('validateProhibitedTerm detects invalid regular expressions', () => {
    const invalidRegex = validateProhibitedTerm({
      term_or_pattern: '[unclosed-brace',
      explanation: 'Regex error test',
      is_regex: true,
    })
    assert.strictEqual(invalidRegex.valid, false)
    assert.match(invalidRegex.error || '', /Invalid regular expression/)

    const validRegex = validateProhibitedTerm({
      term_or_pattern: '\\b(cheap|knockoff)\\b',
      explanation: 'Regex test',
      is_regex: true,
    })
    assert.strictEqual(validRegex.valid, true)
  })

  test('validatePreferredWording validates avoid term, preferred term, and explanation', () => {
    assert.strictEqual(
      validatePreferredWording({ avoid_term: '', preferred_term: 'crisp audio', explanation: 'exp' }).valid,
      false
    )
    assert.strictEqual(
      validatePreferredWording({ avoid_term: 'loud audio', preferred_term: '', explanation: 'exp' }).valid,
      false
    )
    assert.strictEqual(
      validatePreferredWording({ avoid_term: 'loud audio', preferred_term: 'high fidelity', explanation: '' }).valid,
      false
    )
    assert.strictEqual(
      validatePreferredWording({
        avoid_term: 'loud audio',
        preferred_term: 'high fidelity',
        explanation: 'Maintains luxury brand tone',
      }).valid,
      true
    )
  })

  test('validateApprovedFact requires all core fields', () => {
    assert.strictEqual(
      validateApprovedFact({ entity: '', attribute: 'Driver', approved_value: '40mm', explanation: 'exp' }).valid,
      false
    )
    assert.strictEqual(
      validateApprovedFact({ entity: 'NovaSound Pulse', attribute: '', approved_value: '40mm', explanation: 'exp' }).valid,
      false
    )
    assert.strictEqual(
      validateApprovedFact({ entity: 'NovaSound Pulse', attribute: 'Driver', approved_value: '', explanation: 'exp' }).valid,
      false
    )
    assert.strictEqual(
      validateApprovedFact({
        entity: 'NovaSound Pulse',
        attribute: 'Driver',
        approved_value: '40mm Beryllium',
        explanation: 'Engineered hardware spec',
      }).valid,
      true
    )
  })

  test('validateRequiredDisclaimer validates trigger pattern and regex validity', () => {
    assert.strictEqual(
      validateRequiredDisclaimer({
        trigger_description: '',
        trigger_pattern: 'battery life',
        required_disclaimer_text: '*Results may vary',
        explanation: 'Legal disclaimer',
      }).valid,
      false
    )

    assert.strictEqual(
      validateRequiredDisclaimer({
        trigger_description: 'Battery claims',
        trigger_pattern: '(?<=unclosed',
        required_disclaimer_text: '*Results may vary',
        explanation: 'Legal disclaimer',
      }).valid,
      false
    )

    assert.strictEqual(
      validateRequiredDisclaimer({
        trigger_description: 'Battery claims',
        trigger_pattern: '\\b(30-hour|all-day battery)\\b',
        required_disclaimer_text: '*Actual battery life varies based on volume and ANC settings.',
        explanation: 'Required for consumer testing claims',
      }).valid,
      true
    )
  })

  test('validateFullBrandRules checks complete configuration structure', () => {
    const validConfig: BrandRulesConfig = {
      brand_name: 'NovaSound Audio',
      description: 'Premium acoustic products',
      voice_and_tone: 'Sophisticated and authoritative',
      is_demo: true,
      prohibited_terms: [
        {
          id: 'p1',
          term_or_pattern: 'cheap',
          is_regex: false,
          case_sensitive: false,
          severity: 'critical',
          explanation: 'Degrades brand equity',
          suggested_replacement: 'accessible luxury',
        },
      ],
      preferred_wording: [
        {
          id: 'pw1',
          avoid_term: 'noise isolation',
          preferred_term: 'Active Acoustic Shielding',
          case_sensitive: false,
          severity: 'info',
          explanation: 'Branded terminology',
        },
      ],
      approved_facts: [
        {
          id: 'f1',
          entity: 'NovaSound Studio Pro',
          attribute: 'Battery Life',
          approved_value: '30 hours',
          severity: 'critical',
          explanation: 'Official hardware spec',
        },
      ],
      required_disclaimers: [
        {
          id: 'd1',
          trigger_description: 'Battery Claims',
          trigger_pattern: '30-hour battery',
          required_disclaimer_text: '*Tested at 50% volume with ANC active.',
          case_sensitive: false,
          severity: 'warning',
          explanation: 'Legal compliance',
        },
      ],
    }

    const validResult = validateFullBrandRules(validConfig)
    assert.strictEqual(validResult.valid, true)
    assert.strictEqual(validResult.errors.length, 0)

    const invalidConfig: BrandRulesConfig = {
      ...validConfig,
      brand_name: '   ',
      prohibited_terms: [
        {
          id: 'p2',
          term_or_pattern: '',
          is_regex: false,
          case_sensitive: false,
          severity: 'critical',
          explanation: '',
        },
      ],
    }

    const invalidResult = validateFullBrandRules(invalidConfig)
    assert.strictEqual(invalidResult.valid, false)
    assert.strictEqual(invalidResult.errors.length >= 2, true)
  })
})
