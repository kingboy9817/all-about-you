# Lens

This file is read by `engine/provider/allaboutme_provider.py`. Keep the first fenced
`yaml` block valid: the provider extracts that block and passes these keys to the
engine.

```yaml
# Hard filters are deal-breakers applied before fit scoring.
hard_filters:
  # A listing location passes when it contains one of these tokens, unless remote_ok
  # is true and the listing itself is explicitly remote.
  allowed_locations: ["remote", "united states"]
  remote_ok: true
  # Use null until the user confirms a hard compensation floor.
  comp_floor: null
  # Lowercase terms that should reject a role when found in org/title/location/industry.
  exclude: ["gambling"]

# Soft weights are available to prompts and future scoring logic. Keep values numeric.
soft_weights:
  automation: 3
  stakeholder_communication: 3
  product_operations: 4
  travel_tolerance: 1

# Tier thresholds are consumed by rules.assign_tier.
tier_thresholds:
  deep: 0.75
  light: 0.5

# Eligibility is consumed by rules.geo_gate during verify.
eligibility:
  # Placeholder work authorization tokens. Replace with the user's real tokens.
  work_auth: ["united states"]
  # Full working languages use the language name. Partial levels can use suffixes
  # such as spanish-basic.
  languages: ["english"]
```

## Prompt-only placeholders

- Target domains: `{{user's priority domains}}`
- Compensation normalization: `{{currency and cadence rules for this user's search}}`
- Motivation tiers: `{{roles to pursue hard, roles to monitor, roles to reject}}`
