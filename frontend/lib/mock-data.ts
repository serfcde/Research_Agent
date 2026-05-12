import type { AgentNode, ResearchReport, ResearchRun } from "@/types/research";

export const agentTemplate: AgentNode[] = [
  { id: "prompt", name: "Prompt Enhancer", role: "Clarifies topics and scope", status: "idle", progress: 0 },
  { id: "planner", name: "Planner Agent", role: "Builds task graph", status: "idle", progress: 0 },
  { id: "worker", name: "Worker Agent", role: "Runs parallel research", status: "idle", progress: 0 },
  { id: "web", name: "Web Search Tool", role: "Collects cited sources", status: "idle", progress: 0 },
  { id: "formatter", name: "Formatter Agent", role: "Composes final report", status: "idle", progress: 0 }
];

export const examplePrompts = [
  "Research Quantum Computing and Edge AI",
  "Compare autonomous AI agents and robotic process automation",
  "Research AI in healthcare and blockchain in banking",
  "Analyze climate tech batteries and green hydrogen"
];

export const mockReport: ResearchReport = {
  id: "ars-20260511-qc-edge",
  title: "Research Report: Quantum Computing and Edge AI",
  topics: ["Quantum Computing", "Edge AI"],
  introduction:
    "This report examines two infrastructure-shaping technologies: quantum computing, which targets new classes of computational advantage, and edge AI, which moves inference and adaptation closer to real-world devices.",
  sections: {
    "Quantum Computing":
      "Quantum computing is moving from pure laboratory experimentation toward specialized commercial pilots. The highest-value use cases cluster around optimization, materials simulation, cryptography readiness, and pharmaceutical discovery. Near-term systems remain constrained by error rates, coherence windows, and integration complexity, but the ecosystem is maturing through cloud access, hybrid algorithms, and better tooling.",
    "Edge AI":
      "Edge AI is accelerating because enterprises want lower latency, lower cloud cost, stronger privacy posture, and resilient offline operation. The category spans cameras, industrial gateways, mobile devices, vehicles, and medical hardware. Progress is driven by compact models, neural accelerators, quantization, and orchestration platforms that manage fleets of intelligent devices."
  },
  comparativeAnalysis:
    "Quantum computing is a strategic, long-horizon capability with breakthrough potential in narrow computational domains. Edge AI is a near-term deployment pattern already changing operations across industrial, healthcare, retail, and mobility environments. Together they illustrate the split between frontier compute discovery and distributed intelligence at the point of action.",
  keyInsights: [
    "Edge AI has clearer near-term ROI because it reduces latency and cloud dependency in deployed systems.",
    "Quantum computing remains technically constrained but strategically important for simulation-heavy industries.",
    "Both fields depend on mature tooling, talent pipelines, and trust frameworks before broad adoption.",
    "Hybrid architectures are the practical path: cloud coordination, edge inference, and specialized accelerators."
  ],
  conclusion:
    "Organizations should treat edge AI as an immediate product and operations lever while tracking quantum computing through focused pilots, ecosystem partnerships, and cryptography readiness programs.",
  citations: [
    {
      title: "Enterprise AI Infrastructure Outlook",
      url: "https://example.com/ai-infrastructure",
      snippet: "Analysis of distributed inference, accelerators, and enterprise adoption patterns."
    },
    {
      title: "Quantum Computing Commercialization Review",
      url: "https://example.com/quantum-review",
      snippet: "Overview of quantum hardware, algorithms, and industry pilots."
    }
  ],
  generatedAt: new Date().toISOString(),
  totalWords: 1840,
  filePath: "/research_outputs/research_quantum_edge.txt"
};

export const mockHistory: ResearchRun[] = [
  {
    id: "ars-20260511-qc-edge",
    prompt: "Research Quantum Computing and Edge AI",
    depth: "medium",
    status: "completed",
    progress: 100,
    currentTask: "Report ready",
    createdAt: new Date().toISOString(),
    estimatedCompletion: "Complete",
    tokenUsage: { prompt: 8210, completion: 14850, total: 23060 },
    agents: agentTemplate.map((agent) => ({ ...agent, status: "completed", progress: 100 })),
    logs: [],
    tools: [],
    report: mockReport
  },
  {
    id: "ars-20260510-health-bank",
    prompt: "Research AI in healthcare and blockchain in banking",
    depth: "deep",
    status: "completed",
    progress: 100,
    currentTask: "Report ready",
    createdAt: new Date(Date.now() - 86400000).toISOString(),
    estimatedCompletion: "Complete",
    tokenUsage: { prompt: 11120, completion: 24440, total: 35560 },
    agents: agentTemplate.map((agent) => ({ ...agent, status: "completed", progress: 100 })),
    logs: [],
    tools: [],
    report: { ...mockReport, id: "ars-20260510-health-bank", title: "Research Report: AI in Healthcare and Blockchain in Banking", topics: ["AI in Healthcare", "Blockchain in Banking"] }
  }
];
