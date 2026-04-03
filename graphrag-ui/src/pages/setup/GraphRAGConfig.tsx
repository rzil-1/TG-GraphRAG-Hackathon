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

const GraphRAGConfig = () => {
  const [reuseEmbedding, setReuseEmbedding] = useState(false);
  const [eccUrl, setEccUrl] = useState("http://graphrag-ecc:8001");
  const [chatHistoryUrl, setChatHistoryUrl] = useState("http://chat-history:8002");
  
  // Default chunker (used when no chunker specified in document)
  const [defaultChunker, setDefaultChunker] = useState("semantic");
  
  // Retrieval settings
  const [topK, setTopK] = useState("5");
  const [numHops, setNumHops] = useState("2");

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

  useEffect(() => {
    fetchConfig();
  }, []);


  const fetchConfig = async () => {
    setIsLoading(true);
    try {
      const creds = localStorage.getItem("creds");
      const response = await fetch("/ui/config", {
        headers: { Authorization: `Basic ${creds}` },
      });

      if (!response.ok) {
        throw new Error("Failed to fetch configuration");
      }

      const data = await response.json();
      const graphragConfig = data.graphrag_config;

      if (graphragConfig) {
        setReuseEmbedding(graphragConfig.reuse_embedding || false);
        setEccUrl(graphragConfig.ecc || "http://graphrag-ecc:8001");
        setChatHistoryUrl(graphragConfig.chat_history_api || "http://chat-history:8002");
        setDefaultChunker(graphragConfig.chunker || "semantic");
        setTopK(String(graphragConfig.top_k ?? 5));
        setNumHops(String(graphragConfig.num_hops ?? 2));

        const chunkerConfig = graphragConfig.chunker_config || {};
        setChunkSize(String(chunkerConfig.chunk_size || 1024));
        setOverlapSize(String(chunkerConfig.overlap_size || 0));
        setSemanticMethod(chunkerConfig.method || "percentile");
        setSemanticThreshold(String(chunkerConfig.threshold || 0.95));
        setRegexPattern(chunkerConfig.pattern || "\\r?\\n");
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
      const creds = localStorage.getItem("creds");
      
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
      
      const graphragConfigData = {
        reuse_embedding: reuseEmbedding,
        ecc: eccUrl,
        chat_history_api: chatHistoryUrl,
        chunker: defaultChunker,
        chunker_config: chunkerConfig,
        top_k: parseInt(topK),
        num_hops: parseInt(numHops),
      };

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

