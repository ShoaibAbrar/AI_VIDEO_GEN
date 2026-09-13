import React from 'react'
import { useHealthCheck } from '../hooks/useApi'
import { SystemHealthData } from '../types'
import { Database, Cpu as GpuIcon, Activity, Sparkles } from 'lucide-react'

export const HealthStatus: React.FC = () => {
  const { data, isLoading, error } = useHealthCheck() as { data?: SystemHealthData; isLoading: boolean; error: any }

  if (isLoading) {
    return (
      <div className="inline-flex items-center gap-2 px-3 py-1.5 bg-slate-900/90 border border-slate-800 rounded-full text-slate-400 text-xs font-medium animate-pulse">
        <Activity className="w-3.5 h-3.5 text-indigo-400 animate-spin" />
        <span>Syncing engine status...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="inline-flex items-center gap-2 px-3 py-1 bg-rose-950/40 border border-rose-800/60 rounded-full text-rose-300 text-xs font-medium">
        <span className="w-2 h-2 rounded-full bg-rose-500 animate-ping"></span>
        <span>Backend Offline</span>
      </div>
    )
  }

  const isApiHealthy = data?.status === 'healthy'
  const isDbHealthy = data?.database === 'healthy'
  const isGpuAvailable = Boolean(data?.gpu?.available)
  const gpuName = data?.gpu?.device_name || (isGpuAvailable ? 'GPU Active' : 'No GPU')
  const isWan2GpReady = Boolean(data?.wan2gp?.available)
  const modelsAvail = data?.wan2gp?.models_available ?? 0

  return (
    <div className="flex flex-wrap items-center gap-2 text-xs font-medium">
      {/* API Badge */}
      <div
        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border transition-all ${
          isApiHealthy
            ? 'bg-emerald-950/40 border-emerald-800/50 text-emerald-300'
            : 'bg-amber-950/40 border-amber-800/50 text-amber-300'
        }`}
        title="API Gateway Status"
      >
        <span className={`w-1.5 h-1.5 rounded-full ${isApiHealthy ? 'bg-emerald-400' : 'bg-amber-400'}`}></span>
        <span>API: {data?.status || 'ok'}</span>
      </div>

      {/* Database Badge */}
      <div
        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border transition-all ${
          isDbHealthy
            ? 'bg-emerald-950/40 border-emerald-800/50 text-emerald-300'
            : 'bg-rose-950/40 border-rose-800/50 text-rose-300'
        }`}
        title="Database Status"
      >
        <Database className="w-3 h-3 opacity-70" />
        <span>DB: {data?.database || 'ok'}</span>
      </div>

      {/* GPU Badge */}
      <div
        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border transition-all ${
          isGpuAvailable
            ? 'bg-indigo-950/50 border-indigo-700/60 text-indigo-200'
            : 'bg-slate-900/80 border-slate-800 text-slate-400'
        }`}
        title="GPU Runtime Hardware"
      >
        <GpuIcon className="w-3 h-3 text-indigo-400" />
        <span>GPU: {gpuName}</span>
      </div>

      {/* Engine Status Badge */}
      <div
        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border transition-all ${
          isWan2GpReady
            ? 'bg-blue-950/50 border-blue-700/60 text-blue-200'
            : 'bg-slate-900/80 border-slate-800 text-slate-400'
        }`}
        title="Internal Wan2GP Engine Status"
      >
        <Sparkles className="w-3 h-3 text-blue-400" />
        <span>Engine: Wan2GP ({isWan2GpReady ? `${modelsAvail} Ready` : 'Dev Mode'})</span>
      </div>
    </div>
  )
}
