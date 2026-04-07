import React, { useState, useEffect } from "react";
import { Settings, Save, Loader2 } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import ConfigScopeToggle from "@/components/ConfigScopeToggle";

const GraphRAGConfig = () => {
  const [selectedGraph, setSelectedGraph] = useState(sessionStorage.getItem("selectedGraph") || "");
  const [availableGraphs, setAvailableGraphs] = useState<string[]>([]);
  const [reuseEmbedding, setReuseEmbedding] = useState(false);
  const [eccUrl, setEccUrl] = useState("http://graphrag-ecc:8001");
  const [chatHistoryUrl, setChatHistoryUrl] = useState("http://chat-history:8002");

  // Default chunker (used when no chunker specified in document)
  const [defaultChunker, setDefaultChunker] = useState("semantic");

  // Retrieval settings
  const [topK, setTopK] = useState("5");
  const [numHops, setNumHops] = useState("2");
  const [numSeenMin, setNumSeenMin] = useState("2");
  const [communityLevel, setCommunityLevel] = useState("2");
  const [docOnly, setDocOnly] = useState(false);

  // Advanced ingestion settings
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [loadBatchSize, setLoadBatchSize] = useState("500");
  const [upsertDelay, setUpsertDelay] = useState("0");
  const [maxConcurrency, setMaxConcurrency] = useState("10");

  // Chunker-specific settings
  const [chunkSize, setChunkSize] = useState("1024");
  const [overlapSize, setOverlapSize] = useState("0");
  const [semanticMethod, setSemanticMethod] = useState("percentile");
  const [semanticThreshold, setSemanticThreshold] = useState("0.95");
  const [regexPattern, setRegexPattern] = useState("\\r?\\n");

  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [messageType, setMessageType] = useState<"success" | "error" | "">("");

  // Scope: "global" edits global config, "graph" edits per-graph overrides
  const [configScope, setConfigScope] = useState<"global" | "graph">("global");
  const [graphOverrides, setGraphOverrides] = useState<Record<string, any>>({});

  useEffect(() => {
    const site = JSON.parse(sessionStorage.getItem("site") || "{}");
    setAvailableGraphs(site.graphs || []);
    fetchConfig();
  }, []);


  const applyGraphragConfig = (graphragConfig: any) => {
    if (!graphragConfig) return;
    setReuseEmbedding(graphragConfig.reuse_embedding || false);
    setEccUrl(graphragConfig.ecc || "http://graphrag-ecc:8001");
    setChatHistoryUrl(graphragConfig.chat_history_api || "http://chat-history:8002");
    setDefaultChunker(graphragConfig.chunker || "semantic");
    setTopK(String(graphragConfig.top_k ?? 5));
    setNumHops(String(graphragConfig.num_hops ?? 2));
    setNumSeenMin(String(graphragConfig.num_seen_min ?? 2));
    setCommunityLevel(String(graphragConfig.community_level ?? 2));
    setDocOnly(graphragConfig.doc_only || false);
    setLoadBatchSize(String(graphragConfig.load_batch_size ?? 500));
    setUpsertDelay(String(graphragConfig.upsert_delay ?? 0));
    setMaxConcurrency(String(graphragConfig.default_concurrency ?? 10));

    const chunkerConfig = graphragConfig.chunker_config || {};
    setChunkSize(String(chunkerConfig.chunk_size || 1024));
    setOverlapSize(String(chunkerConfig.overlap_size || 0));
    setSemanticMethod(chunkerConfig.method || "percentile");
    setSemanticThreshold(String(chunkerConfig.threshold || 0.95));
    setRegexPattern(chunkerConfig.pattern || "\\r?\\n");
  };

  const fetchConfig = async (scope?: "global" | "graph", graphname?: string) => {
    setIsLoading(true);
    const effectiveScope = scope ?? configScope;
    const effectiveGraph = graphname ?? selectedGraph;
    try {
      const creds = sessionStorage.getItem("creds");
      const params = new URLSearchParams();
      if (effectiveGraph) params.set("graphname", effectiveGraph);
      if (effectiveScope === "graph") params.set("scope", "graph");
      const queryString = params.toString() ? `?${params.toString()}` : "";
      const response = await fetch(`/ui/config${queryString}`, {
        headers: { Authorization: `Basic ${creds}` },
      });

      if (!response.ok) {
        throw new Error("Failed to fetch configuration");
      }

      const data = await response.json();

      if (effectiveScope === "graph" && data.graphrag_overrides) {
        setGraphOverrides(data.graphrag_overrides);
        // Show per-graph values: merge global + overrides for display
        const merged = { ...data.graphrag_config, ...data.graphrag_overrides };
        applyGraphragConfig(merged);
      } else {
        setGraphOverrides({});
        applyGraphragConfig(data.graphrag_config);
      }
    } catch (error: any) {
      console.error("Error fetching config:", error);
      setMessage(`Failed to load configuration: ${error.message}`);
      setMessageType("error");
    } finally {
      setIsLoading(false);
    }
  };

  const handleSave = async () => {
    setIsSaving(true);
    setMessage("");
    setMessageType("");

    try {
      const creds = sessionStorage.getItem("creds");
      
      // Prepare chunker config based on selected chunker type
      const chunkerConfig: any = {};
      
      if (defaultChunker === "character" || defaultChunker === "markdown" || defaultChunker === "recursive") {
        chunkerConfig.chunk_size = parseInt(chunkSize);
        chunkerConfig.overlap_size = parseInt(overlapSize);
      } else if (defaultChunker === "semantic") {
        chunkerConfig.method = semanticMethod;
        chunkerConfig.threshold = parseFloat(semanticThreshold);
      } else if (defaultChunker === "regex") {
        chunkerConfig.pattern = regexPattern;
      } else if (defaultChunker === "html") {
        // HTML chunker doesn't require specific config in the current implementation
        // but we keep it consistent
      }
      
      const graphragConfigData: any = {
        reuse_embedding: reuseEmbedding,
        ecc: eccUrl,
        chat_history_api: chatHistoryUrl,
        chunker: defaultChunker,
        chunker_config: chunkerConfig,
        top_k: parseInt(topK),
        num_hops: parseInt(numHops),
        num_seen_min: parseInt(numSeenMin),
        community_level: parseInt(communityLevel),
        doc_only: docOnly,
        load_batch_size: parseInt(loadBatchSize),
        upsert_delay: parseInt(upsertDelay),
        default_concurrency: parseInt(maxConcurrency),
      };

      if (configScope === "graph") {
        graphragConfigData.scope = "graph";
        graphragConfigData.graphname = selectedGraph;
      }

      const response = await fetch("/ui/config/graphrag", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Basic ${creds}`,
        },
        body: JSON.stringify(graphragConfigData),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Failed to save GraphRAG configuration");
      }

      const result = await response.json();
      setMessage(result.message || "GraphRAG configuration saved successfully!");
      setMessageType("success");
      
      // Auto-hide success message after 3 seconds
      setTimeout(() => {
        setMessage("");
        setMessageType("");
      }, 3000);
    } catch (error: any) {
      console.error("Error saving GraphRAG config:", error);
      setMessage(`❌ Error: ${error.message}`);
      setMessageType("error");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="p-8">
      <div className="max-w-5xl mx-auto">
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-12 h-12 rounded-full bg-tigerOrange/10 flex items-center justify-center">
              <Settings className="h-6 w-6 text-tigerOrange" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-black dark:text-white">
                GraphRAG Configuration
              </h1>
              <p className="text-sm text-gray-600 dark:text-[#D9D9D9]">
                Configure GraphRAG-specific parameters and processing settings
              </p>
            </div>
          </div>
        </div>

        {/* Config Scope Toggle */}
        <ConfigScopeToggle
          configScope={configScope}
          selectedGraph={selectedGraph}
          availableGraphs={availableGraphs}
          onScopeChange={(scope) => {
            setConfigScope(scope);
            if (scope === "global") {
              fetchConfig("global");
            } else if (selectedGraph) {
              fetchConfig("graph", selectedGraph);
            }
          }}
          onGraphChange={(value) => {
            setConfigScope("graph");
            setSelectedGraph(value);
            sessionStorage.setItem("selectedGraph", value);
            window.dispatchEvent(new Event("graphrag:selectedGraph"));
            fetchConfig("graph", value);
          }}
          graphSelectedHint={
            Object.keys(graphOverrides).length > 0
              ? `Overridden keys: ${Object.keys(graphOverrides).join(", ")}. Other settings are inherited from global.`
              : "No per-graph overrides set. All settings are inherited from global defaults."
          }
        />

        {/* Success/Error Message */}
        {message && (
          <div
            className={`p-4 rounded-lg mb-6 ${
              messageType === "success"
                ? "bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-300 border border-green-200 dark:border-green-800"
                : "bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 border border-red-200 dark:border-red-800"
            }`}
          >
            {message}
          </div>
        )}

        <fieldset>
        <div className="space-y-6">
          {/* General Settings */}
          <div className="bg-white dark:bg-shadeA border border-gray-300 dark:border-[#3D3D3D] rounded-lg p-6">
            <h2 className="text-lg font-semibold mb-4 text-black dark:text-white">
              General Settings
            </h2>
            <p className="text-sm text-gray-600 dark:text-[#D9D9D9] mb-6">
              Configure general GraphRAG parameters.
            </p>

            <div className="space-y-4">
              <div>
                <div className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    id="reuseEmbedding"
                    className="rounded border-gray-300 dark:border-[#3D3D3D]"
                    checked={reuseEmbedding}
                    onChange={(e) => setReuseEmbedding(e.target.checked)}
                  />
                  <label htmlFor="reuseEmbedding" className="text-sm font-medium text-black dark:text-white">
                    Reuse Embedding
                  </label>
                </div>
                <p className="text-xs text-gray-600 dark:text-[#D9D9D9] mt-1 ml-6">
                  Skip fetching new embedding if embedding is already attached to it
                </p>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-2 text-black dark:text-white">
                    Top K
                  </label>
                  <Input
                    type="number"
                    min="1"
                    className="dark:border-[#3D3D3D] dark:bg-background"
                    placeholder="5"
                    value={topK}
                    onChange={(e) => setTopK(e.target.value)}
                  />
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    Number of top similar results to retrieve during search
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2 text-black dark:text-white">
                    Number of Hops
                  </label>
                  <Input
                    type="number"
                    min="1"
                    className="dark:border-[#3D3D3D] dark:bg-background"
                    placeholder="2"
                    value={numHops}
                    onChange={(e) => setNumHops(e.target.value)}
                  />
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    Number of graph hops to traverse when expanding retrieved results
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-2 text-black dark:text-white">
                    Min Seen Count
                  </label>
                  <Input
                    type="number"
                    min="1"
                    className="dark:border-[#3D3D3D] dark:bg-background"
                    placeholder="2"
                    value={numSeenMin}
                    onChange={(e) => setNumSeenMin(e.target.value)}
                  />
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    Minimum times a node must appear across retrievals to be included in results
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2 text-black dark:text-white">
                    Community Level
                  </label>
                  <Input
                    type="number"
                    min="1"
                    className="dark:border-[#3D3D3D] dark:bg-background"
                    placeholder="2"
                    value={communityLevel}
                    onChange={(e) => setCommunityLevel(e.target.value)}
                  />
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    Community hierarchy level used for community search
                  </p>
                </div>
              </div>

              <div>
                <div className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    id="docOnly"
                    className="rounded border-gray-300 dark:border-[#3D3D3D]"
                    checked={docOnly}
                    onChange={(e) => setDocOnly(e.target.checked)}
                  />
                  <label htmlFor="docOnly" className="text-sm font-medium text-black dark:text-white">
                    Document Only Search
                  </label>
                </div>
                <p className="text-xs text-gray-600 dark:text-[#D9D9D9] mt-1 ml-6">
                  Retrieve original documents instead of document chunks in results
                </p>
              </div>
            </div>
          </div>

          {/* Chunker Settings */}
          <div className="bg-white dark:bg-shadeA border border-gray-300 dark:border-[#3D3D3D] rounded-lg p-6">
            <h2 className="text-lg font-semibold mb-4 text-black dark:text-white">
              Chunker Settings
            </h2>
            <p className="text-sm text-gray-600 dark:text-[#D9D9D9] mb-6">
              Configure document chunking for ingestion
            </p>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-2 text-black dark:text-white">
                  Default Chunker
                </label>
                <Select value={defaultChunker} onValueChange={setDefaultChunker}>
                  <SelectTrigger className="dark:border-[#3D3D3D] dark:bg-background">
                    <SelectValue placeholder="Select default chunker" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="semantic">Semantic Chunker</SelectItem>
                    <SelectItem value="character">Character Chunker</SelectItem>
                    <SelectItem value="regex">Regex Chunker</SelectItem>
                    <SelectItem value="markdown">Markdown Chunker</SelectItem>
                    <SelectItem value="html">HTML Chunker</SelectItem>
                    <SelectItem value="recursive">Recursive Chunker</SelectItem>
                  </SelectContent>
                </Select>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  Used when no chunker is specified for a document
                </p>
              </div>

              {/* Settings for character/markdown/recursive chunkers */}
              {(defaultChunker === "character" || defaultChunker === "markdown" || defaultChunker === "recursive") && (
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium mb-2 text-black dark:text-white">
                      Chunk Size
                    </label>
                    <Input
                      type="number"
                      className="dark:border-[#3D3D3D] dark:bg-background"
                      placeholder="1024"
                      value={chunkSize}
                      onChange={(e) => setChunkSize(e.target.value)}
                    />
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                      Maximum size of each chunk
                    </p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium mb-2 text-black dark:text-white">
                      Overlap Size
                    </label>
                    <Input
                      type="number"
                      className="dark:border-[#3D3D3D] dark:bg-background"
                      placeholder="0"
                      value={overlapSize}
                      onChange={(e) => setOverlapSize(e.target.value)}
                    />
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                      Overlap between consecutive chunks
                    </p>
                  </div>
                </div>
              )}

              {/* Settings for semantic chunker */}
              {defaultChunker === "semantic" && (
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium mb-2 text-black dark:text-white">
                      Semantic Method
                    </label>
                    <Select value={semanticMethod} onValueChange={setSemanticMethod}>
                      <SelectTrigger className="dark:border-[#3D3D3D] dark:bg-background">
                        <SelectValue placeholder="Select method" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="percentile">Percentile</SelectItem>
                        <SelectItem value="standard_deviation">Standard Deviation</SelectItem>
                        <SelectItem value="interquartile">Interquartile</SelectItem>
                      </SelectContent>
                    </Select>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                      Breakpoint detection method
                    </p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium mb-2 text-black dark:text-white">
                      Semantic Threshold
                    </label>
                    <Input
                      type="number"
                      step="0.01"
                      className="dark:border-[#3D3D3D] dark:bg-background"
                      placeholder="0.95"
                      value={semanticThreshold}
                      onChange={(e) => setSemanticThreshold(e.target.value)}
                    />
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                      Threshold for detecting breakpoints
                    </p>
                  </div>
                </div>
              )}

              {/* Settings for regex chunker */}
              {defaultChunker === "regex" && (
                <div>
                  <label className="block text-sm font-medium mb-2 text-black dark:text-white">
                    Regex Pattern
                  </label>
                  <Input
                    type="text"
                    className="dark:border-[#3D3D3D] dark:bg-background"
                    placeholder="\r?\n"
                    value={regexPattern}
                    onChange={(e) => setRegexPattern(e.target.value)}
                  />
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    Regular expression pattern to split on
                  </p>
                </div>
              )}

              {/* Info for HTML chunker */}
              {defaultChunker === "html" && (
                <div className="p-4 rounded-lg bg-blue-50 dark:bg-blue-900/20 text-blue-800 dark:text-blue-200">
                  <p className="text-sm">
                    HTML chunker uses the document structure to split content. No additional configuration needed.
                  </p>
                </div>
              )}
            </div>
          </div>

          {message && (
            <div
              className={`p-4 rounded-lg ${
                messageType === "success"
                  ? "bg-green-50 dark:bg-green-900/20 text-green-800 dark:text-green-200"
                  : "bg-red-50 dark:bg-red-900/20 text-red-800 dark:text-red-200"
              }`}
            >
              {message}
            </div>
          )}

          {/* Advanced Ingestion Settings */}
          <div className="bg-white dark:bg-shadeA border border-gray-300 dark:border-[#3D3D3D] rounded-lg p-6">
            <button
              type="button"
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="w-full flex items-center justify-between"
            >
              <h2 className="text-lg font-semibold text-black dark:text-white">
                Advanced Ingestion Settings
              </h2>
              <span className="text-sm text-gray-500 dark:text-gray-400">
                {showAdvanced ? "▲ Collapse" : "▼ Expand"}
              </span>
            </button>
            {!showAdvanced && (
              <p className="text-sm text-gray-600 dark:text-[#D9D9D9] mt-2">
                Performance tuning for document ingestion and batch processing.
              </p>
            )}

            {showAdvanced && (
              <div className="space-y-4 mt-4">
                <p className="text-sm text-gray-600 dark:text-[#D9D9D9] mb-2">
                  Performance tuning for document ingestion and batch processing.
                </p>

                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <label className="block text-sm font-medium mb-2 text-black dark:text-white">
                      Batch Size
                    </label>
                    <Input
                      type="number"
                      min="1"
                      className="dark:border-[#3D3D3D] dark:bg-background"
                      placeholder="500"
                      value={loadBatchSize}
                      onChange={(e) => setLoadBatchSize(e.target.value)}
                    />
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                      Vertices per upsert batch
                    </p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium mb-2 text-black dark:text-white">
                      Upsert Delay
                    </label>
                    <Input
                      type="number"
                      min="0"
                      className="dark:border-[#3D3D3D] dark:bg-background"
                      placeholder="0"
                      value={upsertDelay}
                      onChange={(e) => setUpsertDelay(e.target.value)}
                    />
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                      Seconds between batches
                    </p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium mb-2 text-black dark:text-white">
                      Default Concurrency
                    </label>
                    <Input
                      type="number"
                      min="1"
                      className="dark:border-[#3D3D3D] dark:bg-background"
                      placeholder="10"
                      value={maxConcurrency}
                      onChange={(e) => setMaxConcurrency(e.target.value)}
                    />
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                      Max concurrent workers for graph queries, LLM, and embedding calls
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Service Endpoints (global only) */}
          {configScope !== "graph" && (
            <div className="bg-white dark:bg-shadeA border border-gray-300 dark:border-[#3D3D3D] rounded-lg p-6">
              <h2 className="text-lg font-semibold mb-4 text-black dark:text-white">
                Service Endpoints
              </h2>
              <p className="text-sm text-gray-600 dark:text-[#D9D9D9] mb-6">
                Configure internal service URLs. These are global settings and cannot be overridden per graph.
              </p>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-2 text-black dark:text-white">
                    ECC Service URL
                  </label>
                  <Input
                    type="text"
                    className="dark:border-[#3D3D3D] dark:bg-background"
                    placeholder="http://graphrag-ecc:8001"
                    value={eccUrl}
                    onChange={(e) => setEccUrl(e.target.value)}
                  />
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    Entity-Context-Community service endpoint
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2 text-black dark:text-white">
                    Chat History API URL
                  </label>
                  <Input
                    type="text"
                    className="dark:border-[#3D3D3D] dark:bg-background"
                    placeholder="http://chat-history:8002"
                    value={chatHistoryUrl}
                    onChange={(e) => setChatHistoryUrl(e.target.value)}
                  />
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    Chat history service endpoint
                  </p>
                </div>
              </div>
            </div>
          )}

          <Button onClick={handleSave} disabled={isSaving} className="gradient text-white w-full">
            {isSaving ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <Save className="h-4 w-4 mr-2" />
                Save GraphRAG Configuration
              </>
            )}
          </Button>
        </div>
        </fieldset>
      </div>
    </div>
  );
};

export default GraphRAGConfig;

