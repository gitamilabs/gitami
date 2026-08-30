import { create } from "zustand";
import { Citation, ToolStep, SSEEvent, AIServiceConfig } from "../lib/types";
import { aiApi } from "../lib/api";

export interface DisplayMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  toolSteps?: ToolStep[];
  citations?: Citation[];
  thoughts?: string[];
  latencyMs?: number;
  isStreaming?: boolean;
}

interface ChatState {
  selectedRepo: string;
  selectedBranch: string;
  messages: DisplayMessage[];
  isStreaming: boolean;
  activeThoughts: string[];
  activeToolSteps: ToolStep[];
  activeCitations: Citation[];
  activeAnswerDelta: string;
  currentLatency: number;
  error: string | null;
  abortController: AbortController | null;
  aiConfig: AIServiceConfig | null;

  setSelectedRepo: (repo: string) => void;
  setSelectedBranch: (branch: string) => void;
  clearMessages: () => void;
  sendMessage: (text: string) => Promise<void>;
  stopStreaming: () => void;
  fetchAIConfig: () => Promise<void>;
}

export const useChatStore = create<ChatState>((set, get) => ({
  selectedRepo: "",
  selectedBranch: "main",
  messages: [
    {
      id: "welcome-msg",
      role: "assistant",
      content:
        "Hello! I am your **Sentinel Autonomous Codebase Intelligence Assistant**. I can trace functions across repositories, run AST call graph traversals in Neo4j, calculate ripple blast radius, and retrieve semantic vector passages. Ask me anything about your codebase!",
      timestamp: new Date().toISOString(),
    },
  ],
  isStreaming: false,
  activeThoughts: [],
  activeToolSteps: [],
  activeCitations: [],
  activeAnswerDelta: "",
  currentLatency: 0,
  error: null,
  abortController: null,
  aiConfig: null,

  fetchAIConfig: async () => {
    try {
      const cfg = await aiApi.getConfig();
      set({ aiConfig: cfg });
    } catch (e) {
      console.warn("Could not fetch AI service config:", e);
    }
  },

  setSelectedRepo: (repo: string) => set({ selectedRepo: repo }),
  setSelectedBranch: (branch: string) => set({ selectedBranch: branch }),

  clearMessages: () =>
    set({
      messages: [],
      activeThoughts: [],
      activeToolSteps: [],
      activeCitations: [],
      activeAnswerDelta: "",
      error: null,
    }),

  stopStreaming: () => {
    const { abortController } = get();
    if (abortController) {
      abortController.abort();
    }
    set({ isStreaming: false, abortController: null });
  },

  sendMessage: async (text: string) => {
    const { selectedRepo, selectedBranch, messages, isStreaming } = get();
    if (!text.trim() || isStreaming) return;
    if (!selectedRepo) {
      set({ error: "Select an indexed repository before starting a chat." });
      return;
    }

    const userMessage: DisplayMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: text,
      timestamp: new Date().toISOString(),
    };

    const assistantPlaceholderId = `assistant-${Date.now()}`;
    const initialAssistantMsg: DisplayMessage = {
      id: assistantPlaceholderId,
      role: "assistant",
      content: "",
      timestamp: new Date().toISOString(),
      toolSteps: [],
      citations: [],
      thoughts: [],
      isStreaming: true,
    };

    const controller = new AbortController();

    set({
      messages: [...messages, userMessage, initialAssistantMsg],
      isStreaming: true,
      activeThoughts: [],
      activeToolSteps: [],
      activeCitations: [],
      activeAnswerDelta: "",
      currentLatency: 0,
      error: null,
      abortController: controller,
    });

    const historyPayload = messages
      .filter((m) => m.content.trim() !== "")
      .slice(-6)
      .map((m) => ({ role: m.role, content: m.content }));

    let answerAccumulator = "";
    const thoughtsAccumulator: string[] = [];
    const toolStepsAccumulator: ToolStep[] = [];
    let citationsAccumulator: Citation[] = [];
    let latencyAccumulator = 0;

    const handleEvent = (event: SSEEvent) => {
      switch (event.type) {
        case "thought": {
          thoughtsAccumulator.push(event.content);
          set({
            activeThoughts: [...thoughtsAccumulator],
          });
          break;
        }

        case "tool_start": {
          const newStep: ToolStep = {
            id: event.step_id,
            tool_name: event.tool_name,
            title: event.title,
            status: "running",
            latency_ms: 0,
            args: event.args || {},
            summary: "Executing tool query...",
            raw_output: {},
            step_index: event.step_index,
          };
          const existingIdx = toolStepsAccumulator.findIndex(
            (s) => s.id === event.step_id
          );
          if (existingIdx >= 0) {
            toolStepsAccumulator[existingIdx] = newStep;
          } else {
            toolStepsAccumulator.push(newStep);
          }
          set({ activeToolSteps: [...toolStepsAccumulator] });
          break;
        }

        case "tool_end": {
          const completedStep: ToolStep = {
            id: event.step_id,
            tool_name: event.tool_name,
            title: event.title,
            status: event.status || "completed",
            latency_ms: event.latency_ms,
            args: event.args || {},
            summary: event.summary,
            raw_output: event.raw_output,
            step_index: event.step_index,
          };
          const existingIdx = toolStepsAccumulator.findIndex(
            (s) => s.id === event.step_id
          );
          if (existingIdx >= 0) {
            toolStepsAccumulator[existingIdx] = completedStep;
          } else {
            toolStepsAccumulator.push(completedStep);
          }
          set({ activeToolSteps: [...toolStepsAccumulator] });
          break;
        }

        case "answer_delta": {
          answerAccumulator += event.delta;
          set({ activeAnswerDelta: answerAccumulator });
          break;
        }

        case "citations": {
          citationsAccumulator = [...citationsAccumulator, ...event.citations];
          set({ activeCitations: [...citationsAccumulator] });
          break;
        }

        case "done": {
          latencyAccumulator = event.total_latency_ms;
          set({ currentLatency: latencyAccumulator });
          break;
        }

        case "error": {
          set({ error: event.message });
          break;
        }
      }

      // Update in-flight placeholder message
      set((state) => ({
        messages: state.messages.map((m) =>
          m.id === assistantPlaceholderId
            ? {
                ...m,
                content: answerAccumulator,
                thoughts: [...thoughtsAccumulator],
                toolSteps: [...toolStepsAccumulator],
                citations: [...citationsAccumulator],
                latencyMs: latencyAccumulator,
                isStreaming: true,
              }
            : m
        ),
      }));
    };

    const handleError = (err: Error) => {
      console.error("Streaming error:", err);
      const fallbackContent =
        answerAccumulator ||
        `⚠️ Request encountered an error: ${err.message}. Please verify the AI Service connection.`;

      set((state) => ({
        isStreaming: false,
        error: err.message,
        abortController: null,
        messages: state.messages.map((m) =>
          m.id === assistantPlaceholderId
            ? {
                ...m,
                content: fallbackContent,
                thoughts: thoughtsAccumulator,
                toolSteps: toolStepsAccumulator,
                citations: citationsAccumulator,
                isStreaming: false,
              }
            : m
        ),
      }));
    };

    const handleComplete = () => {
      set((state) => ({
        isStreaming: false,
        abortController: null,
        messages: state.messages.map((m) =>
          m.id === assistantPlaceholderId
            ? {
                ...m,
                content:
                  answerAccumulator ||
                  "Completed reasoning and contextual code review.",
                thoughts: thoughtsAccumulator,
                toolSteps: toolStepsAccumulator,
                citations: citationsAccumulator,
                latencyMs: latencyAccumulator,
                isStreaming: false,
              }
            : m
        ),
      }));
    };

    await aiApi.streamChat(
      {
        repo_id: selectedRepo,
        branch: selectedBranch,
        message: text,
        history: historyPayload,
      },
      handleEvent,
      handleError,
      handleComplete,
      controller.signal
    );
  },
}));
