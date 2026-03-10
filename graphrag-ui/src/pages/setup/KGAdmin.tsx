import React, { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Database, Loader2, RefreshCw, Upload } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useConfirm } from "@/hooks/useConfirm";
import { useNavigate } from "react-router-dom";
import IngestGraph from "./IngestGraph";

const KGAdmin = () => {
  const [confirm, confirmDialog] = useConfirm();
  const navigate = useNavigate();
  const [availableGraphs, setAvailableGraphs] = useState<string[]>([]);
  
  // Dialog states
  const [initializeDialogOpen, setInitializeDialogOpen] = useState(false);
  const [refreshDialogOpen, setRefreshDialogOpen] = useState(false);
  const [ingestDialogOpen, setIngestDialogOpen] = useState(false);

  // Reset states when dialogs close
  const handleInitializeDialogChange = (open: boolean) => {
    if (!open && isInitializing) {
      return;
    }
    setInitializeDialogOpen(open);
    if (!open) {
      setGraphName("");
      setStatusMessage("");
      setStatusType("");
    }
  };

  const handleRefreshDialogChange = (open: boolean) => {
    setRefreshDialogOpen(open);
    if (!open) {
      setRefreshMessage("");
    }
  };

  // Initialize state
  const [graphName, setGraphName] = useState("");
  const [isInitializing, setIsInitializing] = useState(false);
  const [statusMessage, setStatusMessage] = useState("");
  const [statusType, setStatusType] = useState<"success" | "error" | "">("");

  // Refresh state
  const [refreshGraphName, setRefreshGraphName] = useState("");
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [refreshMessage, setRefreshMessage] = useState("");
  const [isRebuildRunning, setIsRebuildRunning] = useState(false);
  const [isCheckingStatus, setIsCheckingStatus] = useState(false);

  // Load available graphs
  useEffect(() => {
    const store = JSON.parse(localStorage.getItem("site") || "{}");
    if (store.graphs && Array.isArray(store.graphs)) {
      setAvailableGraphs(store.graphs);
      if (store.graphs.length > 0 && !refreshGraphName) {
        setRefreshGraphName(store.graphs[0]);
      }
    }
  }, []);

  // Initialize Graph
  const handleInitializeGraph = async () => {
    if (!graphName.trim()) {
      setStatusMessage("Please enter a graph name");
      setStatusType("error");
      return;
    }

    setIsInitializing(true);
    setStatusMessage("Creating graph and initializing GraphRAG schema...");
    setStatusType("");

    try {
      const creds = localStorage.getItem("creds");
      if (!creds) {
        throw new Error("Not authenticated. Please login first.");
      }

      setStatusMessage("Step 1/2: Creating graph...");
      const createResponse = await fetch(`/ui/${graphName}/create_graph`, {
        method: "POST",
        headers: { Authorization: `Basic ${creds}` },
      });

      const createData = await createResponse.json();

      if (!createResponse.ok) {
        throw new Error(
          createData.detail ||
            createData.message ||
            `Failed to create graph: ${createResponse.statusText}`
        );
      }

      if (createData.status !== "success") {
        if (createData.message && createData.message.includes("already exists")) {
          const shouldInitialize = await confirm(
            `Graph "${graphName}" already exists. Do you want to initialize it with GraphRAG schema?`
          );
          if (!shouldInitialize) {
            setStatusMessage("Operation cancelled by user.");
            setStatusType("error");
            setIsInitializing(false);
            return;
          }
        } else {
          throw new Error(
            createData.message || `Failed to create graph: ${createData.details}`
          );
        }
      }

      setStatusMessage("Step 2/2: Initializing GraphRAG schema...");
      const initResponse = await fetch(`/ui/${graphName}/initialize_graph`, {
        method: "POST",
        headers: { Authorization: `Basic ${creds}` },
      });

      const initData = await initResponse.json();

      if (!initResponse.ok) {
        throw new Error(
          initData.detail || `Failed to initialize graph: ${initResponse.statusText}`
        );
      }

      if (initData.status !== "success") {
        setStatusMessage(
          initData.message || `Failed to initialize graph: ${initData.details}`
        );
        setStatusType("error");
        setIsInitializing(false);
        return;
      }

      setStatusMessage(
        `✅ Graph "${graphName}" created and initialized successfully!`
      );
      setStatusType("success");

      const store = JSON.parse(localStorage.getItem("site") || "{}");
      if (!store.graphs) {
        store.graphs = [];
      }
      if (!store.graphs.includes(graphName)) {
        store.graphs.push(graphName);
        localStorage.setItem("site", JSON.stringify(store));
        setAvailableGraphs([...store.graphs]);
      }

      setGraphName("");
    } catch (error: any) {
      console.error("Error creating graph:", error);
      setStatusMessage(`❌ Error: ${error.message}`);
      setStatusType("error");
    } finally {
      setIsInitializing(false);
    }
  };

  // Check rebuild status
  const checkRebuildStatus = async (
    graphName: string,
    showLoadingMessage: boolean = false
  ) => {
    if (!graphName) return;

    setIsCheckingStatus(true);
    if (showLoadingMessage) {
      setRefreshMessage("Checking rebuild status...");
    }

    try {
      const creds = localStorage.getItem("creds");
      const statusResponse = await fetch(`/ui/${graphName}/rebuild_status`, {
        method: "GET",
        headers: { Authorization: `Basic ${creds}` },
      });

      if (statusResponse.ok) {
        const statusData = await statusResponse.json();
        const wasRunning = isRebuildRunning;
        const isCurrentlyRunning = statusData.is_running || false;

        setIsRebuildRunning(isCurrentlyRunning);

        if (isCurrentlyRunning) {
          const startTime = statusData.started_at
            ? new Date(statusData.started_at * 1000).toLocaleString()
            : "unknown time";
          setRefreshMessage(
            `⚠️ A rebuild is already in progress for "${graphName}" (started at ${startTime}). Please wait for it to complete.`
          );
        } else {
          if (wasRunning && statusData.status === "completed") {
            setRefreshMessage(
              `✅ Rebuild completed successfully for "${graphName}".`
            );
          } else if (statusData.status === "failed") {
            setRefreshMessage(
              `❌ Previous rebuild failed: ${statusData.error || "Unknown error"}`
            );
          } else {
            if (!showLoadingMessage) {
              setRefreshMessage("");
            }
          }
        }
      }
    } catch (error: any) {
      console.error("Error checking rebuild status:", error);
      setIsRebuildRunning(false);
      setRefreshMessage("");
    } finally {
      setIsCheckingStatus(false);
    }
  };

  // Refresh Graph
  const handleRefreshGraph = async () => {
    if (!refreshGraphName) {
      setRefreshMessage("Please select a graph");
      return;
    }

    if (isRebuildRunning) {
      setRefreshMessage(
        `⚠️ A rebuild is already in progress. Please wait for it to complete.`
      );
      return;
    }

    const shouldRefresh = await confirm(
      `Are you sure you want to refresh the knowledge graph "${refreshGraphName}"? This will rebuild the graph content.`
    );
    if (!shouldRefresh) {
      setRefreshMessage("Operation cancelled by user.");
      return;
    }

    setIsRefreshing(true);
    setRefreshMessage("Submitting rebuild request...");

    try {
      const creds = localStorage.getItem("creds");

      const response = await fetch(`/ui/${refreshGraphName}/rebuild_graph`, {
        method: "POST",
        headers: { Authorization: `Basic ${creds}` },
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(
          errorData.detail || `Failed to refresh graph: ${response.statusText}`
        );
      }

      const data = await response.json();
      console.log("Refresh response:", data);

      setRefreshMessage(
        `✅ Refresh submitted successfully! The knowledge graph "${refreshGraphName}" is being rebuilt.`
      );
      setIsRebuildRunning(true);
    } catch (error: any) {
      console.error("Error refreshing graph:", error);
      setRefreshMessage(`❌ Error: ${error.message}`);
    } finally {
      setIsRefreshing(false);
    }
  };

  // Check status on interval
  useEffect(() => {
    if (refreshDialogOpen && refreshGraphName) {
      checkRebuildStatus(refreshGraphName, true);

      const intervalId = setInterval(() => {
        checkRebuildStatus(refreshGraphName, false);
      }, 5000);

      return () => clearInterval(intervalId);
    }
  }, [refreshDialogOpen, refreshGraphName]);

  return (
    <div className="p-8">
      <div className="max-w-7xl mx-auto">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-black dark:text-white mb-2">
            Knowledge Graph Administration
          </h1>
          <p className="text-sm text-gray-600 dark:text-[#D9D9D9]">
            Configure and manage your knowledge graphs
          </p>
        </div>

        {/* Card Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Initialize Card */}
          <div className="border border-gray-300 dark:border-[#3D3D3D] rounded-lg p-6 bg-white dark:bg-shadeA flex flex-col h-full">
            <div className="mb-4">
              <div className="w-12 h-12 rounded-full bg-tigerOrange/10 flex items-center justify-center mb-4">
                <Database className="h-6 w-6 text-tigerOrange" />
              </div>
              <h2 className="text-lg font-semibold mb-2 text-black dark:text-white">
                Initialize Knowledge Graph
              </h2>
              <p className="text-sm text-gray-600 dark:text-[#D9D9D9] mb-4">
                Create the knowledge graph schema and queries for future document ingestion.
              </p>
            </div>
            <div className="mt-auto pt-4 border-t border-gray-300 dark:border-[#3D3D3D]">
              <Button
                onClick={() => setInitializeDialogOpen(true)}
                className="gradient w-full text-white"
              >
                <Database className="h-4 w-4 mr-2" />
                Initialize Graph
              </Button>
            </div>
          </div>

          {/* Ingest Card */}
          <div className="border border-gray-300 dark:border-[#3D3D3D] rounded-lg p-6 bg-white dark:bg-shadeA flex flex-col h-full">
            <div className="mb-4">
              <div className="w-12 h-12 rounded-full bg-tigerOrange/10 flex items-center justify-center mb-4">
                <Upload className="h-6 w-6 text-tigerOrange" />
              </div>
              <h2 className="text-lg font-semibold mb-2 text-black dark:text-white">
                Ingest to Knowledge Graph
              </h2>
              <p className="text-sm text-gray-600 dark:text-[#D9D9D9] mb-4">
                Upload and ingest documents into your knowledge graph for future content processing.
              </p>
            </div>
            <div className="mt-auto pt-4 border-t border-gray-300 dark:border-[#3D3D3D]">
              <Button
                onClick={() => setIngestDialogOpen(true)}
                className="gradient w-full text-white"
              >
                <Upload className="h-4 w-4 mr-2" />
                Ingest Document
              </Button>
            </div>
          </div>

          {/* Refresh Card */}
          <div className="border border-gray-300 dark:border-[#3D3D3D] rounded-lg p-6 bg-white dark:bg-shadeA flex flex-col h-full">
            <div className="mb-4">
              <div className="w-12 h-12 rounded-full bg-tigerOrange/10 flex items-center justify-center mb-4">
                <RefreshCw className="h-6 w-6 text-tigerOrange" />
              </div>
              <h2 className="text-lg font-semibold mb-2 text-black dark:text-white">
                Refresh Knowledge Graph
              </h2>
              <p className="text-sm text-gray-600 dark:text-[#D9D9D9] mb-4">
                Process new documents in your knowledge graph to refresh its content.
              </p>
            </div>
            <div className="mt-auto pt-4 border-t border-gray-300 dark:border-[#3D3D3D]">
              <Button
                onClick={() => setRefreshDialogOpen(true)}
                className="gradient w-full text-white"
              >
                <RefreshCw className="h-4 w-4 mr-2" />
                Refresh Graph
              </Button>
            </div>
          </div>
        </div>

        {/* Initialize Dialog */}
        <Dialog open={initializeDialogOpen} onOpenChange={handleInitializeDialogChange}>
          <DialogContent
            className="sm:max-w-md"
            onInteractOutside={(e) => {
              if (isInitializing) {
                e.preventDefault();
              }
            }}
          >
            <DialogHeader>
              <DialogTitle>Create New Knowledge Graph</DialogTitle>
              <DialogDescription>
                Enter a name for your new knowledge graph. This will create the graph and initialize the GraphRAG schema.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-2 text-black dark:text-white">
                  Graph Name
                </label>
                <Input
                  placeholder="e.g., MyKnowledgeGraph"
                  value={graphName}
                  onChange={(e) => setGraphName(e.target.value)}
                  disabled={isInitializing}
                  className="dark:border-[#3D3D3D] dark:bg-background"
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !isInitializing) {
                      handleInitializeGraph();
                    }
                  }}
                />
              </div>

              {statusMessage && (
                <div
                  className={`p-3 rounded-lg text-sm ${
                    statusType === "success"
                      ? "bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-300"
                      : statusType === "error"
                      ? "bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300"
                      : "bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300"
                  }`}
                >
                  {statusMessage}
                </div>
              )}

              <div className="flex gap-2 pt-4">
                <Button
                  variant="outline"
                  onClick={() => handleInitializeDialogChange(false)}
                  disabled={isInitializing}
                  className="flex-1"
                >
                  Cancel
                </Button>
                <Button
                  onClick={handleInitializeGraph}
                  disabled={isInitializing || !graphName.trim()}
                  className="gradient text-white flex-1"
                >
                  {isInitializing ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Creating...
                    </>
                  ) : (
                    "Create"
                  )}
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>

        {/* Ingest Dialog */}
        <Dialog open={ingestDialogOpen} onOpenChange={setIngestDialogOpen}>
          <DialogContent className="sm:max-w-4xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Ingest to Knowledge Graph</DialogTitle>
              <DialogDescription>
                Upload and ingest documents into your knowledge graph for future content processing
              </DialogDescription>
            </DialogHeader>
            <IngestGraph isModal={true} />
          </DialogContent>
        </Dialog>

        {/* Refresh Dialog */}
        <Dialog open={refreshDialogOpen} onOpenChange={handleRefreshDialogChange}>
          <DialogContent
            className="sm:max-w-md"
            onInteractOutside={(e) => e.preventDefault()}
          >
            <DialogHeader>
              <DialogTitle>Refresh (Rebuild) Knowledge Graph</DialogTitle>
              <DialogDescription>
                Rebuild and refresh your knowledge graph
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-2 text-black dark:text-white">
                  Select Graph to Refresh
                </label>
                <Select
                  value={refreshGraphName}
                  onValueChange={setRefreshGraphName}
                  disabled={isRefreshing || isRebuildRunning || isCheckingStatus}
                >
                  <SelectTrigger
                    className="dark:border-[#3D3D3D] dark:bg-background"
                    disabled={isRefreshing || isRebuildRunning || isCheckingStatus}
                  >
                    <SelectValue placeholder="Select a graph" />
                  </SelectTrigger>
                  <SelectContent>
                    {availableGraphs.length > 0 ? (
                      availableGraphs.map((graph) => (
                        <SelectItem key={graph} value={graph}>
                          {graph}
                        </SelectItem>
                      ))
                    ) : (
                      <SelectItem value="no-graphs" disabled>
                        No graphs available
                      </SelectItem>
                    )}
                  </SelectContent>
                </Select>
              </div>

              <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg p-3">
                <p className="text-sm text-yellow-800 dark:text-yellow-200 font-medium">
                  ⚠️ Warning
                </p>
                <p className="text-xs text-yellow-700 dark:text-yellow-300 mt-1">
                  This operation will process new documents and rerun community detection that will interrupt related queries.
                </p>
              </div>

              {refreshMessage && (
                <div
                  className={`p-3 rounded-lg text-sm ${
                    refreshMessage.includes("✅")
                      ? "bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-300"
                      : refreshMessage.includes("❌")
                      ? "bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300"
                      : "bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300"
                  }`}
                >
                  {refreshMessage}
                </div>
              )}

              <div className="flex gap-2 pt-4">
                <Button
                  variant="outline"
                  onClick={() => handleRefreshDialogChange(false)}
                  disabled={isRefreshing || isRebuildRunning || isCheckingStatus}
                  className="flex-1"
                >
                  Cancel
                </Button>
                <Button
                  onClick={handleRefreshGraph}
                  disabled={
                    isRefreshing ||
                    !refreshGraphName ||
                    isRebuildRunning ||
                    isCheckingStatus
                  }
                  className="gradient text-white flex-1"
                >
                  {isRefreshing ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Submitting...
                    </>
                  ) : isCheckingStatus ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Checking...
                    </>
                  ) : isRebuildRunning ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Rebuilding...
                    </>
                  ) : (
                    "Rebuild Graph"
                  )}
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </div>
      {confirmDialog}
    </div>
  );
};

export default KGAdmin;
