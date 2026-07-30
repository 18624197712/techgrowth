export type User = { id: string; email: string; totp_enabled: boolean }

export type RubricCriterion = {
  key: string
  label: string
  critical: boolean
}

export type LearningTask = {
  id: string
  title: string
  topic: string
  skill_name: string
  expected_minutes: number
  objective: string
  instructions: string[]
  source_ids: string[]
  submission_kinds: string[]
  rubric: RubricCriterion[]
  status: string
  created_at: string
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
}

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

export type SetupStatus = {
  provider: {
    base_url?: string
    chat_model?: string
    embedding_model?: string
    api_key_configured: boolean
  }
  domain: string
  icp_number: string
  smtp_configured: boolean
  web_push_configured: boolean
  vapid_public_key: string
}

export type NotificationPreference = {
  channel: 'email' | 'web_push'
  event: 'daily_task' | 'review_complete' | 'weekly_review'
  enabled: boolean
}
