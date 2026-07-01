import { apiClient } from "./api/client";

export function mediaUrl(projectRelativePath: string): string {
  return apiClient.mediaUrl(projectRelativePath);
}
