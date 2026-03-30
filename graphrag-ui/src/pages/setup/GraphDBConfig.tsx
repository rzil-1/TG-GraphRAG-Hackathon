import React, { useState, useEffect } from "react";
import { Server, Save, CheckCircle2 } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

const GraphDBConfig = () => {
  const [hostname, setHostname] = useState("http://tigergraph");
  const [restppPort, setRestppPort] = useState("9000");
  const [gsPort, setGsPort] = useState("14240");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [getToken, setGetToken] = useState(false);
  const [defaultTimeout, setDefaultTimeout] = useState("300");
  const [defaultMemThreshold, setDefaultMemThreshold] = useState("5000");
  const [defaultThreadLimit, setDefaultThreadLimit] = useState("8");
  
  // Track original values to detect changes
  const [originalHostname, setOriginalHostname] = useState("");
  const [originalUsername, setOriginalUsername] = useState("");
  
  const [isLoading, setIsLoading] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [connectionTested, setConnectionTested] = useState(false);
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
      const dbConfig = data.db_config;

      if (dbConfig) {
        const loadedHostname = dbConfig.hostname || "http://tigergraph";
        setHostname(loadedHostname);
        setOriginalHostname(loadedHostname); // Track original hostname
        setRestppPort(dbConfig.restppPort || "9000");
        setGsPort(dbConfig.gsPort || "14240");
        
        setUsername(dbConfig.username || "");
        setOriginalUsername(dbConfig.username || "");
        
        setGetToken(dbConfig.getToken || false);
        setDefaultTimeout(String(dbConfig.default_timeout || 300));
        setDefaultMemThreshold(String(dbConfig.default_mem_threshold || 5000));
        setDefaultThreadLimit(String(dbConfig.default_thread_limit || 8));
      }
    } catch (error: any) {
      console.error("Error fetching config:", error);
      setMessage(`Failed to load configuration: ${error.message}`);
      setMessageType("error");
    } finally {
      setIsLoading(false);
    }
  };

  const handleTestConnection = async () => {
    setIsTesting(true);
    setMessage("");
    setMessageType("");
    setConnectionTested(false);

    try {
      const creds = localStorage.getItem("creds");
      const testConfig = {
        hostname,
        restppPort,
        gsPort,
        username,
        password,
        getToken,
      };

      const response = await fetch("/ui/config/db/test", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Basic ${creds}`,
        },
        body: JSON.stringify(testConfig),
      });

      const result = await response.json();

      if (response.ok && result.status === "success") {
        setConnectionTested(true);
        setMessage("Connection successful! You can now save the configuration.");
        setMessageType("success");
      } else {
        setMessage(result.message || "Connection test failed");
        setMessageType("error");
      }
    } catch (error: any) {
      setMessage(`Connection test error: ${error.message}`);
      setMessageType("error");
    } finally {
      setIsTesting(false);
    }
  };

  const handleSave = async () => {
    if (!connectionTested) {
      setMessage("Please test the connection first before saving");
      setMessageType("error");
      return;
    }
    setIsSaving(true);
    setMessage("");
    setMessageType("");

    try {
      const creds = localStorage.getItem("creds");
      const dbConfigData = {
        hostname,
        restppPort,
        gsPort,
        username,
        password,
        getToken,
        default_timeout: parseInt(defaultTimeout),
        default_mem_threshold: parseInt(defaultMemThreshold),
        default_thread_limit: parseInt(defaultThreadLimit),
      };

      const response = await fetch("/ui/config/db", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Basic ${creds}`,
        },
        body: JSON.stringify(dbConfigData),
      });

      const result = await response.json();

      if (response.ok) {
        setMessage("GraphDB configuration saved successfully!");
        setMessageType("success");
        setConnectionTested(false); // Reset after save
        
        // Check if hostname or username changed from what was loaded
        const hostnameChanged = originalHostname && hostname !== originalHostname;
        const usernameChanged = originalUsername && username !== originalUsername;
        
        // If hostname OR username changed, redirect to login so services reconnect
        if (hostnameChanged || usernameChanged) {
          const reason = hostnameChanged 
            ? "GraphDB hostname changed. Please relogin with the new credentials to connect to the new instance."
            : "GraphDB username changed. Please relogin with the new credentials.";
          
          setTimeout(() => {
            // Clear localStorage and redirect to login
            localStorage.removeItem("creds");
            alert(reason);
            window.location.href = "/"; // Redirect to root (login page)
          }, 2000); // Give user 2 seconds to see the success message
        } else {
          // Update originals after successful save (only if no redirect)
          setOriginalHostname(hostname);
          setOriginalUsername(username);
        }
      } else {
        setMessage(result.detail || "Failed to save configuration");
        setMessageType("error");
      }
    } catch (error: any) {
      setMessage(`Save error: ${error.message}`);
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
              <Server className="h-6 w-6 text-tigerOrange" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-black dark:text-white">
                GraphDB Configuration
              </h1>
              <p className="text-sm text-gray-600 dark:text-[#D9D9D9]">
                Configure your TigerGraph database connection and settings
              </p>
            </div>
          </div>
        </div>

        <div className="bg-white dark:bg-shadeA border border-gray-300 dark:border-[#3D3D3D] rounded-lg p-6">
          <fieldset>
            <div className="space-y-6">
            <div>
              <h2 className="text-lg font-semibold mb-4 text-black dark:text-white">
                Database Connection
              </h2>
              <p className="text-sm text-gray-600 dark:text-[#D9D9D9] mb-6">
                Configure your TigerGraph database connection parameters.
              </p>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-2 text-black dark:text-white">
                    Hostname
                  </label>
                  <Input
                    type="text"
                    className="dark:border-[#3D3D3D] dark:bg-background"
                    placeholder="http://tigergraph"
                    value={hostname}
                    onChange={(e) => {
                      setHostname(e.target.value);
                      setConnectionTested(false);
                      setMessage("");
                      setMessageType("");
                    }}
                  />
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    TigerGraph server hostname
                  </p>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium mb-2 text-black dark:text-white">
                      RESTPP Port
                    </label>
                    <Input
                      type="text"
                      className="dark:border-[#3D3D3D] dark:bg-background"
                      placeholder="9000"
                      value={restppPort}
                      onChange={(e) => {
                        setRestppPort(e.target.value);
                        setConnectionTested(false);
                        setMessage("");
                        setMessageType("");
                      }}
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium mb-2 text-black dark:text-white">
                      GS Port
                    </label>
                    <Input
                      type="text"
                      className="dark:border-[#3D3D3D] dark:bg-background"
                      placeholder="14240"
                      value={gsPort}
                      onChange={(e) => {
                        setGsPort(e.target.value);
                        setConnectionTested(false);
                        setMessage("");
                        setMessageType("");
                      }}
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium mb-2 text-black dark:text-white">
                      Username
                    </label>
                    <Input
                      type="text"
                      className="dark:border-[#3D3D3D] dark:bg-background"
                      placeholder="tigergraph"
                      value={username}
                      onChange={(e) => {
                        setUsername(e.target.value);
                        setConnectionTested(false);
                        setMessage("");
                        setMessageType("");
                      }}
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium mb-2 text-black dark:text-white">
                      Password
                    </label>
                    <Input
                      type="password"
                      className="dark:border-[#3D3D3D] dark:bg-background"
                      placeholder="Enter password to test and save"
                      value={password}
                      onChange={(e) => {
                        setPassword(e.target.value);
                        setConnectionTested(false);
                        setMessage("");
                        setMessageType("");
                      }}
                    />
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <label className="block text-sm font-medium mb-2 text-black dark:text-white">
                      Default Timeout
                    </label>
                    <Input
                      type="number"
                      className="dark:border-[#3D3D3D] dark:bg-background"
                      placeholder="300"
                      value={defaultTimeout}
                      onChange={(e) => setDefaultTimeout(e.target.value)}
                    />
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                      Seconds
                    </p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium mb-2 text-black dark:text-white">
                      Memory Threshold
                    </label>
                    <Input
                      type="number"
                      className="dark:border-[#3D3D3D] dark:bg-background"
                      placeholder="5000"
                      value={defaultMemThreshold}
                      onChange={(e) => setDefaultMemThreshold(e.target.value)}
                    />
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                      MB
                    </p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium mb-2 text-black dark:text-white">
                      Thread Limit
                    </label>
                    <Input
                      type="number"
                      className="dark:border-[#3D3D3D] dark:bg-background"
                      placeholder="8"
                      value={defaultThreadLimit}
                      onChange={(e) => setDefaultThreadLimit(e.target.value)}
                    />
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                      Threads
                    </p>
                  </div>
                </div>

                <div className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    id="getToken"
                    className="rounded border-gray-300 dark:border-[#3D3D3D]"
                    checked={getToken}
                    onChange={(e) => {
                      setGetToken(e.target.checked);
                      setConnectionTested(false);
                      setMessage("");
                      setMessageType("");
                    }}
                  />
                  <label htmlFor="getToken" className="text-sm font-medium text-black dark:text-white">
                    Get Token
                  </label>
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

                <div className="flex gap-4">
                  <Button
                    onClick={handleTestConnection}
                    disabled={isTesting || !username || !password}
                    className="bg-blue-600 hover:bg-blue-700 text-white"
                  >
                    <CheckCircle2 className="h-4 w-4 mr-2" />
                    {isTesting ? "Testing..." : "Test Connection"}
                  </Button>

                  <Button
                    onClick={handleSave}
                    disabled={!connectionTested || isSaving}
                    className="gradient text-white"
                  >
                    <Save className="h-4 w-4 mr-2" />
                    {isSaving ? "Saving..." : "Save Configuration"}
                  </Button>
                </div>
              </div>
            </div>
            </div>
          </fieldset>
        </div>
      </div>
    </div>
  );
};

export default GraphDBConfig;

