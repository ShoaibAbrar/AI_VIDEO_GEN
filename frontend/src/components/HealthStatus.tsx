import React from 'react'
import { useHealthCheck } from '../hooks/useApi'

export const HealthStatus: React.FC = () => {
  const { data, isLoading, error } = useHealthCheck()

  if (isLoading) {
    return (
      <div className="inline-block px-4 py-2 bg-gray-200 text-gray-800 rounded">
        Loading...
      </div>
    )
  }

  if (error) {
    return (
      <div className="inline-block px-4 py-2 bg-red-200 text-red-800 rounded">
        Error: Connection failed
      </div>
    )
  }

  const isHealthy = data?.status === 'healthy'
  const dbHealthy = data?.database === 'healthy'

  return (
    <div className="space-y-2">
      <div
        className={`inline-block px-4 py-2 rounded text-white font-semibold ${
          isHealthy ? 'bg-green-600' : 'bg-yellow-600'
        }`}
      >
        API: {data?.status || 'unknown'}
      </div>
      <div
        className={`inline-block px-4 py-2 rounded text-white font-semibold ml-2 ${
          dbHealthy ? 'bg-green-600' : 'bg-red-600'
        }`}
      >
        Database: {data?.database || 'unknown'}
      </div>
      {data?.timestamp && (
        <p className="text-sm text-gray-600">
          Last check: {new Date(data.timestamp).toLocaleTimeString()}
        </p>
      )}
    </div>
  )
}
