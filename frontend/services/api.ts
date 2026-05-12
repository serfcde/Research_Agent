import axios from "axios";
import type { ResearchReport, ResearchRun, StartResearchPayload } from "@/types/research";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "";

export const apiClient = axios.create({
  baseURL: apiBaseUrl,
  timeout: 30000,
  headers: {
    "Content-Type": "application/json"
  }
});

export const researchApi = {
  async start(payload: StartResearchPayload) {
    const { data } = await apiClient.post<ResearchRun>("/api/research/start", payload);
    return data;
  },
  async status(id: string) {
    const { data } = await apiClient.get<ResearchRun>(`/api/research/${id}/status`);
    return data;
  },
  async report(id: string) {
    const { data } = await apiClient.get<ResearchReport>(`/api/research/${id}/report`);
    return data;
  },
  async history() {
    const { data } = await apiClient.get<ResearchRun[]>("/api/research/history");
    return data;
  },
  downloadUrl(id: string) {
    return `${apiBaseUrl}/api/research/${id}/download`;
  },
  streamUrl(id: string) {
    return `${apiBaseUrl}/api/research/${id}/events`;
  }
};
