export type User = { id: string; email: string; totp_enabled: boolean }

export type TaskStep = { action: string; minutes: number; expected_result: string }
export type AcceptanceCheck = {
  method: 'command' | 'inspection' | 'answer'
  instruction: string
  expected_result: string
}
export type RubricCriterion = {
  key: string
  label: string
  description?: string
  critical: boolean
  score_anchors?: Record<string, string>
}

export type LearningTask = {
  id: string
  title: string
  topic: string
  skill_name: string
  expected_minutes: number
  objective: string
  curriculum_version: string
  track_key: string
  stage_key: string
  node_key: string
  track_label: string
  stage_label: string
  node_order: number
  node_total: number
  prerequisites: string[]
  instructions: Array<string | TaskStep>
  source_ids: string[]
  submission_kinds: string[]
  deliverables: string[]
  acceptance_checks: AcceptanceCheck[]
  rubric: RubricCriterion[]
  remediation_hint: string
  task_kind: string
  learning_objectives: string[]
  theory_brief: string
  problem_statement: string
  constraints: string[]
  starter_context: string
  revealed_hints: string[]
  revealed_hint_level: number
  solution_outline: string | null
  solution_revealed_at: string | null
  replaces_task_id: string | null
  regeneration_reason: string
  generation_source: 'ai' | 'rules' | 'legacy'
  guidance_source: 'ai_validated' | 'curriculum_template'
  guidance_reference_ids: string[]
  status: string
  created_at: string
}

export type AnalyticsMetric = {
  key: string
  label: string
  value: number
  unit: string
  definition: string
  components: Record<string, unknown>
}

export type TrackProgress = {
  track_key: string
  label: string
  completed_nodes: number
  total_nodes: number
  current_stage: string
}

export type AnalyticsView = {
  range: '7d' | '30d' | '90d' | 'all'
  metrics: AnalyticsMetric[]
  track_progress?: TrackProgress[]
  topics?: Record<string, number>
  repositories?: Repository[]
}

export type CurriculumTrack = {
  key: string
  label: string
  kind: 'primary' | 'secondary'
  completed_nodes: number
  total_nodes: number
  current_stage: string
  stages: CurriculumStage[]
}

export type CurriculumStage = {
  key: 'foundation' | 'practice' | 'production' | 'architecture'
  label: string
  nodes: Array<{ key: string; order: number; title: string; completed: boolean }>
}

export type CurriculumState = {
  active_track_key: string
  target_stage: 'foundation' | 'practice' | 'production' | 'architecture'
  algorithm_days_per_week: number
  catalog_version: string
  tracks: CurriculumTrack[]
}

export type RadarItem = {
  id: string
  title: string
  summary: string
  source_url: string
  source_name: string
  topic: string
  credibility: number
  relevance: number
  relevance_reason: string
  published_at: string
  created_at: string
}

export type RadarStatus = {
  id: string
  status: 'never' | 'running' | 'succeeded' | 'partial' | 'failed'
  successful_sources: number
  total_sources: number
  failed_sources: string[]
  inserted_items: number
  embedding_failures: number
  created_at: string | null
}

export type ChatIntent =
  | 'technical_qa'
  | 'task_coaching'
  | 'submission_improvement'
  | 'growth_planning'
  | 'radar_to_task'

export type ChatEvent =
  | { type: 'intent'; intent: ChatIntent; confidence: number; needs_action: boolean }
  | { type: 'token'; text: string }
  | { type: 'action_proposal'; id: string; summary: string; expires_at: string }
  | { type: 'tool_call'; id: string; name: string; arguments: Record<string, unknown> }
  | { type: 'tool_result'; id: string; name: string; result: Record<string, unknown> }
  | { type: 'error'; code: string; message: string }
  | { type: 'done' }

export type SkillProfile = {
  id: string
  name: string
  level: 'discovering' | 'practicing' | 'applied' | 'proficient'
  evidence_count: number
  updated_at: string
}

export type Repository = {
  id: string
  device_id: string | null
  name: string
  provider: string
  provider_id: string | null
  canonical_remote: string | null
  local_fingerprint: string
  match_status: 'matched' | 'unmatched' | 'ambiguous'
  languages: Record<string, number>
  last_commit: string
  last_synced_at: string | null
}

export type WeeklyReview = {
  id: string
  summary: string
  evidence_ids: string[]
  next_focus: string[]
  created_at: string
}

export type ProviderEndpointStatus = {
  base_url: string
  model: string
  api_key_configured: boolean
}

export type SetupStatus = {
  provider: { chat: ProviderEndpointStatus; embedding: ProviderEndpointStatus }
  domain: string
  icp_number: string
  smtp_configured: boolean
  web_push_configured: boolean
  github: { configured: boolean }
  vapid_public_key: string
}

export type NotificationPreference = {
  channel: 'email' | 'web_push'
  event: 'daily_task' | 'review_complete' | 'weekly_review'
  enabled: boolean
}
