export interface WSMessage {
  type: string;
  data: Record<string, any>;
  timestamp?: string;
}

export interface TranscriptEntry {
  id: string;
  role: 'user' | 'megan';
  text: string;
  timestamp: Date;
}

export interface ToolExecution {
  id: string;
  tool: string;
  input: Record<string, any>;
  output?: string;
  status: 'running' | 'done' | 'error';
  timestamp: Date;
}

export interface ThinkingEntry {
  id: string;
  text: string;
  timestamp: Date;
}

export interface LogicEntry {
  id: string;
  type: 'thought' | 'action' | 'observation';
  text: string;
  timestamp: Date;
}

export interface ConfirmRequest {
  tool_use_id: string;
  tool: string;
  input: Record<string, any>;
}

export interface SystemMetrics {
  cpu: string;
  memory: string;
  nnLoad: string;
}

export type MeganState = 'idle' | 'listening' | 'thinking' | 'speaking' | 'tool_executing';
