import { create } from "zustand";
import { Citation, ToolStep, SSEEvent, AIServiceConfig } from "../lib/types";
import { aiApi } from "../lib/api";

export interface ReasoningItem {
  id: string;
  type: "thought" | "tool";
  text?: string;
  toolStep?: ToolStep;
  status?: "running" | "completed" | "failed";
  latencyMs?: number;
  stepIndex?: number;
}

export interface DisplayMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  toolSteps?: ToolStep[];
  citations?: Citation[];
  thoughts?: string[];
  reasoningTimeline?: ReasoningItem[];
  latencyMs?: number;
  isStreaming?: boolean;
}

export interface ChatThread {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  projectId?: string;
  repoId: string;
  branch: string;
  rootDirectory?: string | null;
  messages: DisplayMessage[];
}

const DEFAULT_WELCOME_MESSAGE: DisplayMessage = {
  id: "welcome-msg",
  role: "assistant",
  content:
    "Hello! I am your **GitAmi Codebase Intelligence Assistant**. I can trace functions across repositories, run AST call graph traversals in Neo4j, calculate ripple blast radius, and retrieve semantic vector passages. What would you like to explore?",
  timestamp: new Date().toISOString(),
};

interface ChatState {
  currentProjectId: string | null;
  selectedRepo: string;
  selectedBranch: string;
  rootDirectory: string | null;
  threads: ChatThread[];
  activeThreadId: string | null;
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

  initProject: (
    projectId: string,
    defaultRepo?: string,
    defaultBranch?: string,
    defaultRootDir?: string | null
  ) => void;
  createNewThread: () => void;
  switchThread: (threadId: string) => void;
  deleteThread: (threadId: string) => void;
  setSelectedRepo: (repo: string) => void;
  setSelectedBranch: (branch: string) => void;
  setRootDirectory: (rootDir: string | null) => void;
  clearMessages: () => void;
  sendMessage: (text: string) => Promise<void>;
  addAssistantMessage: (content: string) => void;
  stopStreaming: () => void;
  fetchAIConfig: () => Promise<void>;
}

function getStoredThreads(projectId: string): ChatThread[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(`gitami_chat_threads_${projectId}`);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function persistThreads(projectId: string, threads: ChatThread[]) {
  if (typeof window === "undefined" || !projectId) return;
  try {
    localStorage.setItem(`gitami_chat_threads_${projectId}`, JSON.stringify(threads));
  } catch (err) {
    console.warn("Failed to persist chat threads to localStorage:", err);
  }
}

export const useChatStore = create<ChatState>((set, get) => ({
  currentProjectId: null,
  selectedRepo: "",
  selectedBranch: "main",
  rootDirectory: null,
  threads: [],
  activeThreadId: null,
  messages: [DEFAULT_WELCOME_MESSAGE],
  isStreaming: false,
  activeThoughts: [],
  activeToolSteps: [],
  activeCitations: [],
  activeAnswerDelta: "",
  currentLatency: 0,
  error: null,
  abortController: null,
  aiConfig: null,

  initProject: (
    projectId: string,
    defaultRepo = "",
    defaultBranch = "main",
    defaultRootDir = null
  ) => {
    const prevProj = get().currentProjectId;
    if (prevProj === projectId && get().threads.length > 0) {
      if (defaultRepo && !get().selectedRepo) {
        set({ selectedRepo: defaultRepo, selectedBranch: defaultBranch, rootDirectory: defaultRootDir });
      }
      return;
    }

    const stored = getStoredThreads(projectId);
    if (stored.length > 0) {
      const active = stored[0];
      set({
        currentProjectId: projectId,
        threads: stored,
        activeThreadId: active.id,
        messages: active.messages && active.messages.length > 0 ? active.messages : [DEFAULT_WELCOME_MESSAGE],
        selectedRepo: active.repoId || defaultRepo,
        selectedBranch: active.branch || defaultBranch,
        rootDirectory: active.rootDirectory ?? defaultRootDir,
      });
    } else {
      const initialThreadId = `thread-${Date.now()}`;
      const initialThread: ChatThread = {
        id: initialThreadId,
        title: "New Chat",
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        projectId,
        repoId: defaultRepo,
        branch: defaultBranch,
        rootDirectory: defaultRootDir,
        messages: [DEFAULT_WELCOME_MESSAGE],
      };
      persistThreads(projectId, [initialThread]);
      set({
        currentProjectId: projectId,
        threads: [initialThread],
        activeThreadId: initialThreadId,
        messages: [DEFAULT_WELCOME_MESSAGE],
        selectedRepo: defaultRepo,
        selectedBranch: defaultBranch,
        rootDirectory: defaultRootDir,
      });
    }
  },

  createNewThread: () => {
    const { currentProjectId, selectedRepo, selectedBranch, rootDirectory, threads } = get();
    const newId = `thread-${Date.now()}`;
    const newThread: ChatThread = {
      id: newId,
      title: "New Chat",
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      projectId: currentProjectId || "default",
      repoId: selectedRepo,
      branch: selectedBranch,
      rootDirectory,
      messages: [DEFAULT_WELCOME_MESSAGE],
    };
    const updated = [newThread, ...threads];
    if (currentProjectId) {
      persistThreads(currentProjectId, updated);
    }
    set({
      threads: updated,
      activeThreadId: newId,
      messages: [DEFAULT_WELCOME_MESSAGE],
      activeThoughts: [],
      activeToolSteps: [],
      activeCitations: [],
      activeAnswerDelta: "",
      error: null,
    });
  },

  switchThread: (threadId: string) => {
    const { threads } = get();
    const target = threads.find((t) => t.id === threadId);
    if (target) {
      set({
        activeThreadId: target.id,
        messages: target.messages && target.messages.length > 0 ? target.messages : [DEFAULT_WELCOME_MESSAGE],
        selectedRepo: target.repoId || get().selectedRepo,
        selectedBranch: target.branch || get().selectedBranch,
        rootDirectory: target.rootDirectory ?? get().rootDirectory,
        activeThoughts: [],
        activeToolSteps: [],
        activeCitations: [],
        activeAnswerDelta: "",
        error: null,
      });
    }
  },

  deleteThread: (threadId: string) => {
    const { threads, activeThreadId, currentProjectId } = get();
    const updated = threads.filter((t) => t.id !== threadId);
    if (currentProjectId) {
      persistThreads(currentProjectId, updated);
    }
    if (activeThreadId === threadId) {
      if (updated.length > 0) {
        const next = updated[0];
        set({
          threads: updated,
          activeThreadId: next.id,
          messages: next.messages,
        });
      } else {
        get().createNewThread();
      }
    } else {
      set({ threads: updated });
    }
  },

  fetchAIConfig: async () => {
    try {
      const cfg = await aiApi.getConfig();
      set({ aiConfig: cfg });
    } catch (e) {
      console.warn("Could not fetch AI service config:", e);
    }
  },

  setSelectedRepo: (repo: string) => {
    set({ selectedRepo: repo });
    const { activeThreadId, threads, currentProjectId } = get();
    if (activeThreadId && currentProjectId) {
      const updated = threads.map((t) =>
        t.id === activeThreadId ? { ...t, repoId: repo } : t
      );
      set({ threads: updated });
      persistThreads(currentProjectId, updated);
    }
  },

  setSelectedBranch: (branch: string) => {
    set({ selectedBranch: branch });
    const { activeThreadId, threads, currentProjectId } = get();
    if (activeThreadId && currentProjectId) {
      const updated = threads.map((t) =>
        t.id === activeThreadId ? { ...t, branch } : t
      );
      set({ threads: updated });
      persistThreads(currentProjectId, updated);
    }
  },

  setRootDirectory: (rootDir: string | null) => {
    set({ rootDirectory: rootDir });
    const { activeThreadId, threads, currentProjectId } = get();
    if (activeThreadId && currentProjectId) {
      const updated = threads.map((t) =>
        t.id === activeThreadId ? { ...t, rootDirectory: rootDir } : t
      );
      set({ threads: updated });
      persistThreads(currentProjectId, updated);
    }
  },

  clearMessages: () => {
    const { activeThreadId, threads, currentProjectId } = get();
    const updatedMessages = [DEFAULT_WELCOME_MESSAGE];
    set({
      messages: updatedMessages,
      activeThoughts: [],
      activeToolSteps: [],
      activeCitations: [],
      activeAnswerDelta: "",
      error: null,
    });
    if (activeThreadId && currentProjectId) {
      const updated = threads.map((t) =>
        t.id === activeThreadId ? { ...t, messages: updatedMessages, title: "New Chat" } : t
      );
      set({ threads: updated });
      persistThreads(currentProjectId, updated);
    }
  },

  addAssistantMessage: (content: string) => {
    const newMsg: DisplayMessage = {
      id: `assistant-${Date.now()}`,
      role: "assistant",
      content,
      timestamp: new Date().toISOString(),
      isStreaming: false,
    };
    const updated = [...get().messages, newMsg];
    set({ messages: updated });
    const { activeThreadId, threads, currentProjectId } = get();
    if (activeThreadId && currentProjectId) {
      const updatedThreads = threads.map((t) =>
        t.id === activeThreadId ? { ...t, messages: updated, updatedAt: new Date().toISOString() } : t
      );
      set({ threads: updatedThreads });
      persistThreads(currentProjectId, updatedThreads);
    }
  },

  stopStreaming: () => {
    const { abortController } = get();
    if (abortController) {
      abortController.abort();
    }
    set({ isStreaming: false, abortController: null });
  },

  sendMessage: async (text: string) => {
    const {
      selectedRepo,
      selectedBranch,
      rootDirectory,
      messages,
      isStreaming,
      activeThreadId,
      threads,
      currentProjectId,
    } = get();

    if (!text.trim() || isStreaming) return;
    if (!selectedRepo) {
      set({ error: "Please select a connected repository to begin querying." });
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
    const updatedMessages = [...messages, userMessage, initialAssistantMsg];

    // Determine thread title if this is the first user message
    let threadTitle = threads.find((t) => t.id === activeThreadId)?.title;
    if (!threadTitle || threadTitle === "New Chat") {
      threadTitle = text.slice(0, 42).trim() + (text.length > 42 ? "…" : "");
    }

    set({
      messages: updatedMessages,
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
      .filter((m) => m.content.trim() !== "" && m.id !== "welcome-msg")
      .slice(-6)
      .map((m) => ({ role: m.role, content: m.content }));

    let answerAccumulator = "";
    const thoughtsAccumulator: string[] = [];
    const toolStepsAccumulator: ToolStep[] = [];
    const reasoningTimelineAccumulator: ReasoningItem[] = [];
    let citationsAccumulator: Citation[] = [];
    let latencyAccumulator = 0;

    const syncThreadMessages = (msgs: DisplayMessage[]) => {
      if (activeThreadId && currentProjectId) {
        const updatedThreads = get().threads.map((t) =>
          t.id === activeThreadId
            ? {
                ...t,
                title: threadTitle || t.title,
                messages: msgs,
                updatedAt: new Date().toISOString(),
              }
            : t
        );
        set({ threads: updatedThreads });
        persistThreads(currentProjectId, updatedThreads);
      }
    };

    const handleEvent = (event: SSEEvent) => {
      switch (event.type) {
        case "thought": {
          thoughtsAccumulator.push(event.content);
          reasoningTimelineAccumulator.push({
            id: `thought-${thoughtsAccumulator.length}-${Date.now()}`,
            type: "thought",
            text: event.content,
            stepIndex: event.step_index,
          });
          set({ activeThoughts: [...thoughtsAccumulator] });
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
            summary: "Executing query...",
            raw_output: {},
            step_index: event.step_index,
          };
          const existingIdx = toolStepsAccumulator.findIndex((s) => s.id === event.step_id);
          if (existingIdx >= 0) {
            toolStepsAccumulator[existingIdx] = newStep;
          } else {
            toolStepsAccumulator.push(newStep);
          }

          const existingTimelineIdx = reasoningTimelineAccumulator.findIndex(
            (item) => item.type === "tool" && item.id === event.step_id
          );
          if (existingTimelineIdx >= 0) {
            reasoningTimelineAccumulator[existingTimelineIdx] = {
              id: event.step_id,
              type: "tool",
              toolStep: newStep,
              status: "running",
              stepIndex: event.step_index,
            };
          } else {
            reasoningTimelineAccumulator.push({
              id: event.step_id,
              type: "tool",
              toolStep: newStep,
              status: "running",
              stepIndex: event.step_index,
            });
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
          const existingIdx = toolStepsAccumulator.findIndex((s) => s.id === event.step_id);
          if (existingIdx >= 0) {
            toolStepsAccumulator[existingIdx] = completedStep;
          } else {
            toolStepsAccumulator.push(completedStep);
          }

          const existingTimelineIdx = reasoningTimelineAccumulator.findIndex(
            (item) => item.type === "tool" && item.id === event.step_id
          );
          if (existingTimelineIdx >= 0) {
            reasoningTimelineAccumulator[existingTimelineIdx] = {
              ...reasoningTimelineAccumulator[existingTimelineIdx],
              toolStep: completedStep,
              status: completedStep.status,
              latencyMs: completedStep.latency_ms,
            };
          } else {
            reasoningTimelineAccumulator.push({
              id: event.step_id,
              type: "tool",
              toolStep: completedStep,
              status: completedStep.status,
              latencyMs: completedStep.latency_ms,
              stepIndex: event.step_index,
            });
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

      // Update in-flight message
      const nextMsgs = get().messages.map((m) =>
        m.id === assistantPlaceholderId
          ? {
              ...m,
              content: answerAccumulator,
              thoughts: [...thoughtsAccumulator],
              toolSteps: [...toolStepsAccumulator],
              reasoningTimeline: [...reasoningTimelineAccumulator],
              citations: [...citationsAccumulator],
              latencyMs: latencyAccumulator,
              isStreaming: true,
            }
          : m
      );
      set({ messages: nextMsgs });
    };

    const handleError = (err: Error) => {
      console.error("Streaming error:", err);
      const fallbackContent =
        answerAccumulator ||
        `⚠️ Request encountered an error: ${err.message}. Please verify the AI Service connection.`;

      const finalMsgs = get().messages.map((m) =>
        m.id === assistantPlaceholderId
          ? {
              ...m,
              content: fallbackContent,
              thoughts: thoughtsAccumulator,
              toolSteps: toolStepsAccumulator,
              reasoningTimeline: reasoningTimelineAccumulator,
              citations: citationsAccumulator,
              isStreaming: false,
            }
          : m
      );

      set({
        isStreaming: false,
        error: err.message,
        abortController: null,
        messages: finalMsgs,
      });

      syncThreadMessages(finalMsgs);
    };

    const handleComplete = () => {
      const finalMsgs = get().messages.map((m) =>
        m.id === assistantPlaceholderId
          ? {
              ...m,
              content: answerAccumulator || "I have analyzed the codebase and completed the query.",
              thoughts: thoughtsAccumulator,
              toolSteps: toolStepsAccumulator,
              reasoningTimeline: reasoningTimelineAccumulator,
              citations: citationsAccumulator,
              latencyMs: latencyAccumulator,
              isStreaming: false,
            }
          : m
      );

      set({
        isStreaming: false,
        abortController: null,
        messages: finalMsgs,
      });

      syncThreadMessages(finalMsgs);
    };

    await aiApi.streamChat(
      {
        repo_id: selectedRepo,
        branch: selectedBranch,
        root_directory: rootDirectory,
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
