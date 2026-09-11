import { useQuery } from '@tanstack/react-query'
import { healthApi } from '../services/api'

export const useHealthCheck = () => {
  return useQuery({
    queryKey: ['health'],
    queryFn: async () => {
      const res = await healthApi.check()
      return res.data
    },
    refetchInterval: 10000, // Refetch every 10 seconds
  })
}
