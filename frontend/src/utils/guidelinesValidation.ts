import type {
  BrandRulesConfig,
  ProhibitedTermRule,
  PreferredWordingRule,
  ApprovedFact,
  RequiredDisclaimerRule,
} from '../types/governance'

export interface ValidationResult {
  valid: boolean
  error?: string
}

export interface FullValidationResult {
  valid: boolean
  errors: string[]
}

/**
 * Validates brand identity information.
 */
export function validateBrandProfile(brandName: string): ValidationResult {
  if (!brandName || !brandName.trim()) {
    return { valid: false, error: 'Brand Name cannot be blank.' }
  }
  return { valid: true }
}

/**
 * Validates a prohibited terminology rule.
 */
export function validateProhibitedTerm(
  item: Partial<ProhibitedTermRule>
): ValidationResult {
  if (!item.term_or_pattern || !item.term_or_pattern.trim()) {
    return { valid: false, error: 'Prohibited term or pattern cannot be empty.' }
  }
  if (!item.explanation || !item.explanation.trim()) {
    return { valid: false, error: 'Explanation is required for reviewer context.' }
  }
  if (item.is_regex) {
    try {
      new RegExp(item.term_or_pattern)
    } catch {
      return { valid: false, error: 'Invalid regular expression pattern.' }
    }
  }
  return { valid: true }
}

/**
 * Validates a preferred wording rule.
 */
export function validatePreferredWording(
  item: Partial<PreferredWordingRule>
): ValidationResult {
  if (!item.avoid_term || !item.avoid_term.trim()) {
    return { valid: false, error: 'Term to avoid cannot be empty.' }
  }
  if (!item.preferred_term || !item.preferred_term.trim()) {
    return { valid: false, error: 'Approved/preferred term cannot be empty.' }
  }
  if (!item.explanation || !item.explanation.trim()) {
    return { valid: false, error: 'Explanation is required.' }
  }
  return { valid: true }
}

/**
 * Validates an approved certified fact.
 */
export function validateApprovedFact(
  item: Partial<ApprovedFact>
): ValidationResult {
  if (!item.entity || !item.entity.trim()) {
    return { valid: false, error: 'Entity name is required.' }
  }
  if (!item.attribute || !item.attribute.trim()) {
    return { valid: false, error: 'Attribute name is required.' }
  }
  if (!item.approved_value || !item.approved_value.trim()) {
    return { valid: false, error: 'Approved value is required.' }
  }
  if (!item.explanation || !item.explanation.trim()) {
    return { valid: false, error: 'Explanation is required.' }
  }
  return { valid: true }
}

/**
 * Validates a required disclaimer rule.
 */
export function validateRequiredDisclaimer(
  item: Partial<RequiredDisclaimerRule>
): ValidationResult {
  if (!item.trigger_description || !item.trigger_description.trim()) {
    return { valid: false, error: 'Trigger description is required.' }
  }
  if (!item.trigger_pattern || !item.trigger_pattern.trim()) {
    return { valid: false, error: 'Trigger pattern is required.' }
  }
  if (!item.required_disclaimer_text || !item.required_disclaimer_text.trim()) {
    return { valid: false, error: 'Required disclaimer text is required.' }
  }
  if (!item.explanation || !item.explanation.trim()) {
    return { valid: false, error: 'Explanation is required.' }
  }
  try {
    new RegExp(item.trigger_pattern)
  } catch {
    return { valid: false, error: 'Invalid regular expression for trigger pattern.' }
  }
  return { valid: true }
}

/**
 * Validates the complete BrandRulesConfig structure.
 */
export function validateFullBrandRules(rules: BrandRulesConfig): FullValidationResult {
  const errors: string[] = []

  const profileRes = validateBrandProfile(rules.brand_name)
  if (!profileRes.valid && profileRes.error) {
    errors.push(profileRes.error)
  }

  rules.prohibited_terms.forEach((r, idx) => {
    const res = validateProhibitedTerm(r)
    if (!res.valid && res.error) {
      errors.push(`Prohibited term #${idx + 1} (${r.term_or_pattern || 'empty'}): ${res.error}`)
    }
  })

  rules.preferred_wording.forEach((r, idx) => {
    const res = validatePreferredWording(r)
    if (!res.valid && res.error) {
      errors.push(`Preferred wording #${idx + 1} (${r.avoid_term || 'empty'}): ${res.error}`)
    }
  })

  rules.approved_facts.forEach((f, idx) => {
    const res = validateApprovedFact(f)
    if (!res.valid && res.error) {
      errors.push(`Approved fact #${idx + 1} (${f.entity || 'empty'}): ${res.error}`)
    }
  })

  rules.required_disclaimers.forEach((d, idx) => {
    const res = validateRequiredDisclaimer(d)
    if (!res.valid && res.error) {
      errors.push(`Required disclaimer #${idx + 1} (${d.trigger_description || 'empty'}): ${res.error}`)
    }
  })

  return {
    valid: errors.length === 0,
    errors,
  }
}
