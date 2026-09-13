export interface ModelAvailability {
  available: boolean
  reason?: string | null
  missing_files?: string[]
}

export interface ModelMetadata {
  model_type: string
  name: string
  description?: string
  availability?: ModelAvailability
}

export interface GenerationJob {
  id: string
  status: 'QUEUED' | 'PROCESSING' | 'COMPLETED' | 'FAILED' | 'CANCELLED'
  prompt: string
  model_type: string
  video_length?: number | null
  num_inference_steps?: number | null
  seed?: number | null
  progress: number | null
  current_step: number | null
  total_steps: number | null
  phase: string | null
  status_text: string | null
  output_available: boolean
  error_message: string | null
  created_at: string
  completed_at: string | null
}

export interface RoleSummary {
  id: number
  name: string
  description?: string
}

export interface UserSummary {
  id: number
  username: string
  email: string
  first_name?: string
  last_name?: string
  is_active: boolean
  created_at?: string
  last_login?: string | null
  roles: RoleSummary[]
}

export interface GpuInfo {
  available: boolean
  cuda_available: boolean
  device_name: string | null
  vram_total_mb: number | null
  vram_free_mb: number | null
  torch_version: string | null
  cuda_version: string | null
}

export interface Wan2GpStatus {
  available: boolean
  reason?: string | null
  models_total: number
  models_available: number
}

export interface SystemHealthData {
  status: string
  timestamp: string
  database: string
  gpu?: GpuInfo
  wan2gp?: Wan2GpStatus
}

export interface ToastMessage {
  id: string
  type: 'success' | 'error' | 'info' | 'warning'
  title: string
  message?: string
}
