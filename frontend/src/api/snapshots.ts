import type {
  InterfaceListResponse,
  NeighborListResponse,
  SnapshotDeviceListResponse,
  SnapshotResponse,
  VlanListResponse,
} from '../types/api'
import { api, normalizeApiError } from './client'

export async function getSnapshot(snapshotId: string): Promise<SnapshotResponse> {
  try {
    const response = await api.get<SnapshotResponse>(
      `/api/v1/snapshots/${snapshotId}`,
    )
    return response.data
  } catch (error) {
    throw new Error(normalizeApiError(error))
  }
}

export async function listSnapshotDevices(
  snapshotId: string,
): Promise<SnapshotDeviceListResponse> {
  try {
    const response = await api.get<SnapshotDeviceListResponse>(
      `/api/v1/snapshots/${snapshotId}/devices`,
    )
    return response.data
  } catch (error) {
    throw new Error(normalizeApiError(error))
  }
}

export async function listDeviceInterfaces(
  snapshotId: string,
  deviceId: string,
): Promise<InterfaceListResponse> {
  try {
    const response = await api.get<InterfaceListResponse>(
      `/api/v1/snapshots/${snapshotId}/devices/${deviceId}/interfaces`,
    )
    return response.data
  } catch (error) {
    throw new Error(normalizeApiError(error))
  }
}

export async function listDeviceVlans(
  snapshotId: string,
  deviceId: string,
): Promise<VlanListResponse> {
  try {
    const response = await api.get<VlanListResponse>(
      `/api/v1/snapshots/${snapshotId}/devices/${deviceId}/vlans`,
    )
    return response.data
  } catch (error) {
    throw new Error(normalizeApiError(error))
  }
}

export async function listDeviceNeighbors(
  snapshotId: string,
  deviceId: string,
): Promise<NeighborListResponse> {
  try {
    const response = await api.get<NeighborListResponse>(
      `/api/v1/snapshots/${snapshotId}/devices/${deviceId}/neighbors`,
    )
    return response.data
  } catch (error) {
    throw new Error(normalizeApiError(error))
  }
}
