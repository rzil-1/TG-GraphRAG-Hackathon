import React, { useState, useEffect } from "react";
import { Server, CheckCircle2, Save, Loader2 } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

// Type definitions for provider fields
interface FieldConfig {
  key: string;
  label: string;
  type: string;
  required?: boolean;
  placeholder?: string;
}

interface ProviderConfig {
  authFields: FieldConfig[];
  configFields: FieldConfig[];
  note?: string;
}

// Provider-specific field configuration
const PROVIDER_FIELDS: Record<string, ProviderConfig> = {
  openai: {
    authFields: [
      { key: "OPENAI_API_KEY", label: "API Key", type: "password", required: true }
    ],
    configFields: []
  },
  azure: {
    authFields: [
      { key: "AZURE_OPENAI_API_KEY", label: "Azure OpenAI API Key", type: "password", required: true },
      { key: "AZURE_OPENAI_ENDPOINT", label: "Azure Endpoint", type: "text", required: true, placeholder: "https://your-resource.openai.azure.com/" },
      { key: "OPENAI_API_VERSION", label: "API Version", type: "text", required: true, placeholder: "2024-02-15-preview" }
    ],
    configFields: [
      { key: "azure_deployment", label: "Azure Deployment Name", type: "text", required: true, placeholder: "gpt-4" }
    ]
  },
  genai: {
    authFields: [
      { key: "GOOGLE_API_KEY", label: "Google API Key", type: "password", required: true }
    ],
    configFields: []
  },
  vertexai: {
    authFields: [],
    configFields: [
      { key: "project", label: "GCP Project ID (Optional)", type: "text", placeholder: "my-project-id" },
      { key: "location", label: "Location (Optional)", type: "text", placeholder: "us-central1" }
    ],
    note: "VertexAI uses service account credentials from GOOGLE_APPLICATION_CREDENTIALS environment variable"
  },
  bedrock: {
    authFields: [
      { key: "AWS_ACCESS_KEY_ID", label: "AWS Access Key ID", type: "password", required: true },
      { key: "AWS_SECRET_ACCESS_KEY", label: "AWS Secret Access Key", type: "password", required: true }
    ],
    configFields: [
      { key: "region_name", label: "AWS Region", type: "text", required: true, placeholder: "us-east-1" }
    ]
  },
  groq: {
    authFields: [
      { key: "GROQ_API_KEY", label: "Groq API Key", type: "password", required: true }
    ],
    configFields: []
  },
  ollama: {
    authFields: [],
    configFields: [
      { key: "base_url", label: "Ollama Base URL", type: "text", required: true, placeholder: "http://localhost:11434" }
    ]
  },
  sagemaker: {
    authFields: [
      { key: "AWS_ACCESS_KEY_ID", label: "AWS Access Key ID", type: "password", required: true },
      { key: "AWS_SECRET_ACCESS_KEY", label: "AWS Secret Access Key", type: "password", required: true }
    ],
    configFields: [
      { key: "region_name", label: "AWS Region", type: "text", required: true, placeholder: "us-east-1" },
      { key: "endpoint_name", label: "SageMaker Endpoint Name", type: "text", required: true }
    ]
  },
  huggingface: {
    authFields: [
      { key: "HUGGINGFACEHUB_API_TOKEN", label: "HuggingFace API Token", type: "password", required: true }
    ],
    configFields: [
      { key: "endpoint_url", label: "Endpoint URL (Optional)", type: "text", placeholder: "https://api-inference.huggingface.co/models/..." }
    ]
  },
  watsonx: {
    authFields: [
      { key: "WATSONX_API_KEY", label: "IBM WatsonX API Key", type: "password", required: true },
      { key: "WATSONX_URL", label: "WatsonX URL", type: "text", required: true, placeholder: "https://us-south.ml.cloud.ibm.com" },
      { key: "WATSONX_PROJECT_ID", label: "Project ID", type: "text", required: true }
    ],
    configFields: []
  }
};

const LLMConfig = () => {
  const selectedGraph = localStorage.getItem("selectedGraph") || "";
  const [useMultipleProviders, setUseMultipleProviders] = useState(false);
  const [llmConfigAccess, setLlmConfigAccess] = useState<"full" | "chatbot_only">("full");
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [message, setMessage] = useState("");
  const [messageType, setMessageType] = useState<"success" | "error" | "">("");
  const [testResults, setTestResults] = useState<any>(null);
  const [connectionTested, setConnectionTested] = useState(false);
  
  // Single provider state
  const [singleProvider, setSingleProvider] = useState("openai");
  const [singleConfig, setSingleConfig] = useState<Record<string, string>>({});
  const [singleDefaultModel, setSingleDefaultModel] = useState("");
  const [singleChatbotModel, setSingleChatbotModel] = useState("");
  const [singleUseDifferentChatbotModel, setSingleUseDifferentChatbotModel] = useState(false);
  const [singleEmbeddingModel, setSingleEmbeddingModel] = useState("");
  const [multimodalModel, setMultimodalModel] = useState("");
  
  // Multi-provider state
  const [completionProvider, setCompletionProvider] = useState("openai");
  const [completionConfig, setCompletionConfig] = useState<Record<string, string>>({});
  const [completionDefaultModel, setCompletionDefaultModel] = useState("");
  const [completionChatbotModel, setCompletionChatbotModel] = useState("");
  const [completionUseDifferentChatbotModel, setCompletionUseDifferentChatbotModel] = useState(false);
  
  const [embeddingProvider, setEmbeddingProvider] = useState("openai");
  const [embeddingConfig, setEmbeddingConfig] = useState<Record<string, string>>({});
  const [embeddingModel, setEmbeddingModel] = useState("");
  
  const [multimodalProvider, setMultimodalProvider] = useState("openai");
  const [multimodalConfig, setMultimodalConfig] = useState<Record<string, string>>({});
  const [multimodalModelName, setMultimodalModelName] = useState("");
  const isChatbotOnlyMode = llmConfigAccess === "chatbot_only";


  // Fetch current config on mount
  useEffect(() => {
    fetchConfig();
  }, []);

  const fetchConfig = async () => {
    setIsLoading(true);
    try {
      const creds = localStorage.getItem("creds");
      const graphParam = selectedGraph ? `?graphname=${encodeURIComponent(selectedGraph)}` : "";
      const response = await fetch(`/ui/config${graphParam}`, {
        headers: { Authorization: `Basic ${creds}` },
      });

      if (!response.ok) {
        throw new Error("Failed to fetch configuration");
      }

      const data = await response.json();
      const llmConfig = data.llm_config;
      setLlmConfigAccess(data.llm_config_access === "chatbot_only" ? "chatbot_only" : "full");
      const currentDefaultModel = llmConfig.completion_service?.llm_model || "";
      const currentChatbotModel = llmConfig.completion_service?.chatbot_llm || "";
      setSingleDefaultModel(currentDefaultModel);
      setSingleChatbotModel(currentChatbotModel);
      setSingleUseDifferentChatbotModel(
        currentDefaultModel !== "" &&
          currentChatbotModel !== "" &&
          currentDefaultModel !== currentChatbotModel
      );

      // Detect if using multiple providers
      const completionProv = llmConfig.completion_service?.llm_service?.toLowerCase();
      const embeddingProv = llmConfig.embedding_service?.embedding_model_service?.toLowerCase();
      const multimodalProv = llmConfig.multimodal_service?.llm_service?.toLowerCase();
      
      const allSameProvider = 
        completionProv === embeddingProv && 
        (!multimodalProv || completionProv === multimodalProv);
      
      setUseMultipleProviders(!allSameProvider);

      if (!allSameProvider) {
        // Multi-provider mode - Load from backend
        const defaultModel = llmConfig.completion_service?.llm_model || "";
        const chatbotModel = llmConfig.completion_service?.chatbot_llm || "";
        
        setCompletionProvider(completionProv || "openai");
        setCompletionDefaultModel(defaultModel);
        setCompletionChatbotModel(chatbotModel);
        setCompletionUseDifferentChatbotModel(defaultModel !== "" && chatbotModel !== "" && defaultModel !== chatbotModel);
        
        // Load provider-specific config fields
        const completionCfg: Record<string, string> = {};
        if (llmConfig.completion_service?.base_url) completionCfg.base_url = llmConfig.completion_service.base_url;
        if (llmConfig.completion_service?.azure_deployment) completionCfg.azure_deployment = llmConfig.completion_service.azure_deployment;
        if (llmConfig.completion_service?.region_name) completionCfg.region_name = llmConfig.completion_service.region_name;
        if (llmConfig.completion_service?.project) completionCfg.project = llmConfig.completion_service.project;
        if (llmConfig.completion_service?.location) completionCfg.location = llmConfig.completion_service.location;
        if (llmConfig.completion_service?.endpoint_name) completionCfg.endpoint_name = llmConfig.completion_service.endpoint_name;
        if (llmConfig.completion_service?.endpoint_url) completionCfg.endpoint_url = llmConfig.completion_service.endpoint_url;
        setCompletionConfig(completionCfg);

        setEmbeddingProvider(embeddingProv || "openai");
        setEmbeddingModel(llmConfig.embedding_service?.model_name || "");
        
        const embeddingCfg: Record<string, string> = {};
        if (llmConfig.embedding_service?.base_url) embeddingCfg.base_url = llmConfig.embedding_service.base_url;
        if (llmConfig.embedding_service?.azure_deployment) embeddingCfg.azure_deployment = llmConfig.embedding_service.azure_deployment;
        if (llmConfig.embedding_service?.region_name) embeddingCfg.region_name = llmConfig.embedding_service.region_name;
        setEmbeddingConfig(embeddingCfg);

        setMultimodalProvider(multimodalProv || "openai");
        setMultimodalModelName(llmConfig.multimodal_service?.llm_model || "");
        
        const multimodalCfg: Record<string, string> = {};
        if (llmConfig.multimodal_service?.azure_deployment) multimodalCfg.azure_deployment = llmConfig.multimodal_service.azure_deployment;
        setMultimodalConfig(multimodalCfg);
      } else {
        // Single provider mode - Load from backend
        const defaultModel = llmConfig.completion_service?.llm_model || "";
        const chatbotModel = llmConfig.completion_service?.chatbot_llm || "";
        
        setSingleProvider(completionProv || "openai");
        setSingleDefaultModel(defaultModel);
        setSingleChatbotModel(chatbotModel);
        setSingleUseDifferentChatbotModel(defaultModel !== "" && chatbotModel !== "" && defaultModel !== chatbotModel);
        setSingleEmbeddingModel(llmConfig.embedding_service?.model_name || "");
        setMultimodalModel(llmConfig.multimodal_service?.llm_model || "");
        
        // Load provider-specific config fields
        const singleCfg: Record<string, string> = {};
        if (llmConfig.completion_service?.base_url) singleCfg.base_url = llmConfig.completion_service.base_url;
        if (llmConfig.completion_service?.azure_deployment) singleCfg.azure_deployment = llmConfig.completion_service.azure_deployment;
        if (llmConfig.completion_service?.region_name) singleCfg.region_name = llmConfig.completion_service.region_name;
        if (llmConfig.completion_service?.project) singleCfg.project = llmConfig.completion_service.project;
        if (llmConfig.completion_service?.location) singleCfg.location = llmConfig.completion_service.location;
        if (llmConfig.completion_service?.endpoint_name) singleCfg.endpoint_name = llmConfig.completion_service.endpoint_name;
        if (llmConfig.completion_service?.endpoint_url) singleCfg.endpoint_url = llmConfig.completion_service.endpoint_url;
        setSingleConfig(singleCfg);
      }
    } catch (error: any) {
      console.error("Error fetching config:", error);
      setMessage(`Failed to load configuration: ${error.message}`);
      setMessageType("error");
    } finally {
      setIsLoading(false);
    }
  };

  const clearTestResults = () => {
    setConnectionTested(false);
    setTestResults(null);
    setMessage("");
    setMessageType("");
  };

  // Update config when provider changes - CLEAR ALL FIELDS
  const handleProviderChange = (newProvider: string, target: 'single' | 'completion' | 'embedding' | 'multimodal') => {
    if (target === 'single') {
      setSingleProvider(newProvider);
      setSingleConfig({});
      // Clear model names when switching provider
      setSingleDefaultModel("");
      setSingleChatbotModel("");
      setSingleEmbeddingModel("");
      setMultimodalModel("");
    } else if (target === 'completion') {
      setCompletionProvider(newProvider);
      setCompletionConfig({});
      // Clear model names when switching provider
      setCompletionDefaultModel("");
      setCompletionChatbotModel("");
    } else if (target === 'embedding') {
      setEmbeddingProvider(newProvider);
      setEmbeddingConfig({});
      // Clear model name when switching provider
      setEmbeddingModel("");
    } else if (target === 'multimodal') {
      setMultimodalProvider(newProvider);
      setMultimodalConfig({});
      // Clear model name when switching provider
      setMultimodalModelName("");
    }
    clearTestResults();
  };

  const buildAuthConfig = (provider: string, config: Record<string, string>) => {
    const authConfig: Record<string, string> = {};
    const providerFields = PROVIDER_FIELDS[provider as keyof typeof PROVIDER_FIELDS];
    if (!providerFields) return authConfig;
    
    providerFields.authFields.forEach(field => {
      if (config[field.key]) {
        authConfig[field.key] = config[field.key];
      }
    });
    
    return authConfig;
  };

  const buildServiceConfig = (provider: string, config: Record<string, string>) => {
    const serviceConfig: Record<string, any> = {};
    const providerFields = PROVIDER_FIELDS[provider as keyof typeof PROVIDER_FIELDS];
    if (!providerFields) return serviceConfig;
    
    providerFields.configFields.forEach(field => {
      if (config[field.key]) {
        serviceConfig[field.key] = config[field.key];
      }
    });
    
    return serviceConfig;
  };

  const handleSave = async () => {
    setIsSaving(true);
    setMessage("");
    setMessageType("");

    try {
      const creds = localStorage.getItem("creds");
      let llmConfigData: any;

      if (useMultipleProviders) {
        const completionServiceConfig: any = {
          llm_service: completionProvider,
          llm_model: completionDefaultModel,
          authentication_configuration: buildAuthConfig(completionProvider, completionConfig),
          model_kwargs: { temperature: 0 },
          prompt_path: `./common/prompts/${getPromptPath(completionProvider)}/`,
          ...buildServiceConfig(completionProvider, completionConfig)
        };
        
        // Only add chatbot_llm if user wants a different chatbot model
        if (completionUseDifferentChatbotModel && completionChatbotModel && completionChatbotModel !== completionDefaultModel) {
          completionServiceConfig.chatbot_llm = completionChatbotModel;
        }
        
        llmConfigData = {
          graphname: selectedGraph || undefined,
          completion_service: completionServiceConfig,
          embedding_service: {
            embedding_model_service: embeddingProvider,
            model_name: embeddingModel,
            authentication_configuration: buildAuthConfig(embeddingProvider, embeddingConfig),
            ...buildServiceConfig(embeddingProvider, embeddingConfig)
          },
          multimodal_service: {
            llm_service: multimodalProvider,
            llm_model: multimodalModelName,
            authentication_configuration: buildAuthConfig(multimodalProvider, multimodalConfig),
            model_kwargs: { temperature: 0 },
            ...buildServiceConfig(multimodalProvider, multimodalConfig)
          },
        };
      } else {
        const completionServiceConfig: any = {
          llm_service: singleProvider,
          llm_model: singleDefaultModel,
          model_kwargs: { temperature: 0 },
          prompt_path: `./common/prompts/${getPromptPath(singleProvider)}/`,
          ...buildServiceConfig(singleProvider, singleConfig)
        };
        
        // Only add chatbot_llm if user wants a different chatbot model
        if (singleUseDifferentChatbotModel && singleChatbotModel && singleChatbotModel !== singleDefaultModel) {
          completionServiceConfig.chatbot_llm = singleChatbotModel;
        }
        
        llmConfigData = {
          graphname: selectedGraph || undefined,
          authentication_configuration: buildAuthConfig(singleProvider, singleConfig),
          completion_service: completionServiceConfig,
          embedding_service: {
            embedding_model_service: singleProvider,
            model_name: singleEmbeddingModel,
          },
          multimodal_service: {
            llm_service: singleProvider,
            llm_model: multimodalModel,
            model_kwargs: { temperature: 0 },
            ...buildServiceConfig(singleProvider, singleConfig)
          },
        };
      }

      const response = await fetch("/ui/config/llm", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Basic ${creds}`,
        },
        body: JSON.stringify(llmConfigData),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Failed to save configuration");
      }

      setMessage("✅ Configuration saved and reloaded successfully!");
      setMessageType("success");
      setTestResults(null);
      setConnectionTested(false);
    } catch (error: any) {
      console.error("Error saving config:", error);
      setMessage(`❌ Error: ${error.message}`);
      setMessageType("error");
    } finally {
      setIsSaving(false);
    }
  };

  const handleTestConnection = async () => {
    setIsTesting(true);
    setTestResults(null);
    setMessage("");
    setMessageType("");

    try {
      // Frontend validation
      const validateProvider = (provider: string, config: Record<string, string>, serviceName: string) => {
        const providerFields = PROVIDER_FIELDS[provider as keyof typeof PROVIDER_FIELDS];
        if (!providerFields) return null;
        
        for (const field of providerFields.authFields) {
          if (field.required && (!config[field.key] || !config[field.key].trim())) {
            return `${field.label} is required for ${serviceName}`;
          }
        }
        for (const field of providerFields.configFields) {
          if (field.required && (!config[field.key] || !config[field.key].trim())) {
            return `${field.label} is required for ${serviceName}`;
          }
        }
        return null;
      };

      if (useMultipleProviders) {
        const completionError = validateProvider(completionProvider, completionConfig, "Completion Service");
        if (completionError) {
          setMessage(`❌ ${completionError}`);
          setMessageType("error");
          setIsTesting(false);
          return;
        }
        
        const embeddingError = validateProvider(embeddingProvider, embeddingConfig, "Embedding Service");
        if (embeddingError) {
          setMessage(`❌ ${embeddingError}`);
          setMessageType("error");
          setIsTesting(false);
          return;
        }

        const multimodalError = validateProvider(multimodalProvider, multimodalConfig, "Multimodal Service");
        if (multimodalError) {
          setMessage(`❌ ${multimodalError}`);
          setMessageType("error");
          setIsTesting(false);
          return;
        }
      } else {
        const singleError = validateProvider(singleProvider, singleConfig, singleProvider);
        if (singleError) {
          setMessage(`❌ ${singleError}`);
          setMessageType("error");
          setIsTesting(false);
          return;
        }
      }
      
      const creds = localStorage.getItem("creds");
      let llmConfigData: any;

      if (useMultipleProviders) {
        llmConfigData = {
          graphname: selectedGraph || undefined,
          completion_service: {
            llm_service: completionProvider,
            llm_model: completionDefaultModel,
            authentication_configuration: buildAuthConfig(completionProvider, completionConfig),
            ...buildServiceConfig(completionProvider, completionConfig)
          },
          embedding_service: {
            embedding_model_service: embeddingProvider,
            model_name: embeddingModel,
            authentication_configuration: buildAuthConfig(embeddingProvider, embeddingConfig),
            ...buildServiceConfig(embeddingProvider, embeddingConfig)
          },
        };
        
        if (completionUseDifferentChatbotModel && completionChatbotModel !== completionDefaultModel) {
          llmConfigData.chatbot_service = {
            llm_service: completionProvider,
            llm_model: completionChatbotModel,
            authentication_configuration: buildAuthConfig(completionProvider, completionConfig),
            ...buildServiceConfig(completionProvider, completionConfig)
          };
        }
        
        llmConfigData.multimodal_service = {
          llm_service: multimodalProvider,
          llm_model: multimodalModelName,
          authentication_configuration: buildAuthConfig(multimodalProvider, multimodalConfig),
          ...buildServiceConfig(multimodalProvider, multimodalConfig)
        };
      } else {
        llmConfigData = {
          graphname: selectedGraph || undefined,
          authentication_configuration: buildAuthConfig(singleProvider, singleConfig),
          completion_service: {
            llm_service: singleProvider,
            llm_model: singleDefaultModel,
            ...buildServiceConfig(singleProvider, singleConfig)
          },
          embedding_service: {
            embedding_model_service: singleProvider,
            model_name: singleEmbeddingModel,
          },
          multimodal_service: {
            llm_service: singleProvider,
            llm_model: multimodalModel,
            ...buildServiceConfig(singleProvider, singleConfig)
          },
        };
        
        if (singleUseDifferentChatbotModel && singleChatbotModel !== singleDefaultModel) {
          llmConfigData.chatbot_service = {
            llm_service: singleProvider,
            llm_model: singleChatbotModel,
          };
        }
      }

      if (isChatbotOnlyMode) {
        llmConfigData = {
          graphname: selectedGraph || undefined,
          completion_service: {
            chatbot_llm: useDifferentChatbotModel ? chatbotModel : "",
          },
        };
      }

      const response = await fetch("/ui/config/llm/test", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Basic ${creds}`,
        },
        body: JSON.stringify(llmConfigData),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Connection test failed");
      }

      const result = await response.json();
      setTestResults(result.results);
      
      if (result.status === "success") {
        setMessage("✅ All connection tests passed successfully!");
        setMessageType("success");
        setConnectionTested(true);
      } else {
        setMessage("⚠️ Some connection tests failed. See details below.");
        setMessageType("error");
        setConnectionTested(false);
      }
      
    } catch (error: any) {
      console.error("Error testing connection:", error);
      setMessage(`❌ Error: ${error.message}`);
      setMessageType("error");
    } finally {
      setIsTesting(false);
    }
  };

  const getPromptPath = (provider: string) => {
    const providerMap: Record<string, string> = {
      openai: "openai_gpt4",
      azure: "openai_gpt4",
      genai: "google_gemini",
      vertexai: "gcp_vertexai_palm",
      bedrock: "aws_bedrock_claude3haiku",
    };
    return providerMap[provider] || "openai_gpt4";
  };

  // Get placeholder text based on provider
  const getModelPlaceholder = (provider: string, modelType: 'llm' | 'embedding' | 'multimodal') => {
    const placeholders: Record<string, Record<string, string>> = {
      openai: {
        llm: "e.g., gpt-4o-mini, gpt-4o, gpt-4-turbo",
        embedding: "e.g., text-embedding-3-small, text-embedding-3-large",
        multimodal: "e.g., gpt-4o, gpt-4-turbo"
      },
      azure: {
        llm: "e.g., gpt-4, gpt-35-turbo (your deployment name)",
        embedding: "e.g., text-embedding-ada-002 (your deployment name)",
        multimodal: "e.g., gpt-4-vision (your deployment name)"
      },
      genai: {
        llm: "e.g., gemini-1.5-flash, gemini-1.5-pro",
        embedding: "e.g., models/text-embedding-004",
        multimodal: "e.g., gemini-1.5-flash, gemini-1.5-pro"
      },
      vertexai: {
        llm: "e.g., gemini-1.5-flash, text-bison",
        embedding: "e.g., text-embedding-004, textembedding-gecko",
        multimodal: "e.g., gemini-1.5-flash, gemini-pro-vision"
      },
      bedrock: {
        llm: "e.g., anthropic.claude-3-haiku-20240307-v1:0",
        embedding: "e.g., amazon.titan-embed-text-v1",
        multimodal: "e.g., anthropic.claude-3-sonnet-20240229-v1:0"
      },
      groq: {
        llm: "e.g., llama-3.1-70b-versatile, mixtral-8x7b-32768",
        embedding: "Not supported",
        multimodal: "Not supported"
      },
      ollama: {
        llm: "e.g., llama3.2, llama3.1, mistral",
        embedding: "e.g., nomic-embed-text, mxbai-embed-large",
        multimodal: "e.g., llama3.2-vision, llava"
      },
      sagemaker: {
        llm: "Your SageMaker endpoint name",
        embedding: "Not supported",
        multimodal: "Not supported"
      },
      huggingface: {
        llm: "e.g., meta-llama/Meta-Llama-3-8B-Instruct",
        embedding: "Not supported",
        multimodal: "Not supported"
      },
      watsonx: {
        llm: "e.g., ibm/granite-13b-chat-v2",
        embedding: "Not supported",
        multimodal: "Not supported"
      }
    };
    
    return placeholders[provider]?.[modelType] || "Enter model name";
  };

  // Render provider-specific fields
  const renderProviderFields = (provider: string, config: Record<string, string>, setConfig: (config: Record<string, string>) => void) => {
    const providerFields = PROVIDER_FIELDS[provider as keyof typeof PROVIDER_FIELDS];
    if (!providerFields) return null;

    const handleFieldChange = (key: string, value: string) => {
      setConfig({ ...config, [key]: value });
      clearTestResults();
    };

    return (
      <>
        {providerFields.note && (
          <div className="p-3 bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300 text-sm rounded-lg">
            ℹ️ {providerFields.note}
          </div>
        )}
        
        {providerFields.authFields.map(field => (
          <div key={field.key}>
            <label className="block text-sm font-medium mb-2 text-black dark:text-white">
              {field.label} {field.required && <span className="text-red-500">*</span>}
            </label>
            <Input
              type={field.type}
              className="dark:border-[#3D3D3D] dark:bg-background"
              placeholder={field.placeholder || ""}
              value={config[field.key] || ""}
              onChange={(e) => handleFieldChange(field.key, e.target.value)}
            />
          </div>
        ))}
        
        {providerFields.configFields.map(field => (
          <div key={field.key}>
            <label className="block text-sm font-medium mb-2 text-black dark:text-white">
              {field.label} {field.required && <span className="text-red-500">*</span>}
            </label>
            <Input
              type={field.type}
              className="dark:border-[#3D3D3D] dark:bg-background"
              placeholder={field.placeholder || ""}
              value={config[field.key] || ""}
              onChange={(e) => handleFieldChange(field.key, e.target.value)}
            />
          </div>
        ))}
      </>
    );
  };

  const chatbotDefaultModel = useMultipleProviders
    ? completionDefaultModel
    : singleDefaultModel;
  const chatbotModel = useMultipleProviders
    ? completionChatbotModel
    : singleChatbotModel;
  const useDifferentChatbotModel = useMultipleProviders
    ? completionUseDifferentChatbotModel
    : singleUseDifferentChatbotModel;

  if (isLoading) {
    return (
      <div className="p-8 flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-tigerOrange" />
      </div>
    );
  }

  if (isChatbotOnlyMode) {
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
                  LLM Configuration
                </h1>
                <p className="text-sm text-gray-600 dark:text-[#D9D9D9]">
                  You can only update Chatbot model for selected graph.
                </p>
              </div>
            </div>
          </div>

          <div className="space-y-6">
            <div className="bg-white dark:bg-shadeA border border-gray-300 dark:border-[#3D3D3D] rounded-lg p-6">
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-2 text-black dark:text-white">
                    Default LLM Model (Read-only)
                  </label>
                  <Input
                    type="text"
                    className="dark:border-[#3D3D3D] dark:bg-background"
                    value={chatbotDefaultModel}
                    readOnly
                    disabled
                  />
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    This model is configured by global designer/superuser.
                  </p>
                </div>

                <div className="flex items-center space-x-3 mt-3">
                  <input
                    type="checkbox"
                    id="chatbotOnlyUseDifferentChatbot"
                    checked={useDifferentChatbotModel}
                    onChange={(e) => {
                      if (useMultipleProviders) {
                        setCompletionUseDifferentChatbotModel(e.target.checked);
                      } else {
                        setSingleUseDifferentChatbotModel(e.target.checked);
                      }
                      clearTestResults();
                    }}
                    className="h-4 w-4 rounded border-gray-300 dark:border-[#3D3D3D]"
                  />
                  <label htmlFor="chatbotOnlyUseDifferentChatbot" className="text-sm font-medium text-black dark:text-white">
                    Use different model for Chatbot
                  </label>
                </div>

                {useDifferentChatbotModel && (
                  <div>
                    <label className="block text-sm font-medium mb-2 text-black dark:text-white">
                      Chatbot LLM Model
                    </label>
                    <Input
                      type="text"
                      className="dark:border-[#3D3D3D] dark:bg-background"
                      placeholder="e.g. gpt-4.1-mini"
                      value={chatbotModel}
                      onChange={(e) => {
                        if (useMultipleProviders) {
                          setCompletionChatbotModel(e.target.value);
                        } else {
                          setSingleChatbotModel(e.target.value);
                        }
                        clearTestResults();
                      }}
                    />
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                      Leave unchecked to use the default model.
                    </p>
                    <p className="text-xs text-amber-600 dark:text-amber-400 mt-1">
                      Make sure the chatbot model name is exact and supported by your configured provider.
                    </p>
                  </div>
                )}
              </div>
            </div>

            {message && (
              <div
                className={`p-4 rounded-lg text-sm mb-4 ${
                  messageType === "success"
                    ? "bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-300"
                    : "bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300"
                }`}
              >
                {message}
              </div>
            )}

            <div className="flex gap-3">
              <Button
                onClick={handleSave}
                disabled={isSaving || isTesting}
                className="gradient text-white flex-1"
              >
                {isSaving ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Saving...
                  </>
                ) : (
                  <>
                    <Save className="h-4 w-4 mr-2" />
                    Save Configuration
                  </>
                )}
              </Button>
            </div>
          </div>
        </div>
      </div>
    );
  }

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
                LLM Configuration
              </h1>
              <p className="text-sm text-gray-600 dark:text-[#D9D9D9]">
                Configure your Large Language Model provider settings
              </p>
            </div>
          </div>
        </div>

        <fieldset>
        <div className="space-y-6">
          {/* Multi-Provider Toggle */}
          <div className="bg-white dark:bg-shadeA border border-gray-300 dark:border-[#3D3D3D] rounded-lg p-6">
            <div className="flex items-center space-x-3">
              <input
                type="checkbox"
                id="multiProvider"
                checked={useMultipleProviders}
                onChange={(e) => {
                  setUseMultipleProviders(e.target.checked);
                  clearTestResults();
                }}
                className="h-4 w-4 rounded border-gray-300 dark:border-[#3D3D3D]"
              />
              <label htmlFor="multiProvider" className="text-sm font-medium text-black dark:text-white">
                Use different providers for different services
              </label>
            </div>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-2 ml-7">
              Enable this to configure separate providers for chat completion, embeddings, and multimodal services
            </p>
          </div>

          {/* Single Provider Configuration */}
          {!useMultipleProviders && (
            <div className="bg-white dark:bg-shadeA border border-gray-300 dark:border-[#3D3D3D] rounded-lg p-6">
              <div className="space-y-6">
                <div>
                  <h2 className="text-lg font-semibold mb-4 text-black dark:text-white">
                    Provider Settings
                  </h2>
                  <p className="text-sm text-gray-600 dark:text-[#D9D9D9] mb-6">
                    Configure your LLM provider settings for all services.
                  </p>

                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium mb-2 text-black dark:text-white">
                        Provider
                      </label>
                      <Select value={singleProvider} onValueChange={(value) => handleProviderChange(value, 'single')}>
                        <SelectTrigger className="dark:border-[#3D3D3D] dark:bg-background">
                          <SelectValue placeholder="Select provider" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="openai">OpenAI</SelectItem>
                          <SelectItem value="azure">Azure OpenAI</SelectItem>
                          <SelectItem value="genai">Google GenAI (Gemini)</SelectItem>
                          <SelectItem value="vertexai">Google Vertex AI</SelectItem>
                          <SelectItem value="bedrock">AWS Bedrock</SelectItem>
                          <SelectItem value="ollama">Ollama</SelectItem>
                        </SelectContent>
                      </Select>
                      <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                        Only providers supporting both completion and embedding services are shown
                      </p>
                    </div>

                    {renderProviderFields(singleProvider, singleConfig, setSingleConfig)}

                    <div>
                      <label className="block text-sm font-medium mb-2 text-black dark:text-white">
                        Completion Models
                      </label>
                      <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">
                        Configure the LLM models used by the ECC service for document processing (entity extraction and community summarization) and by the chatbot for user query responses
                      </p>
                      
                      <div className="space-y-3 pl-4 border-l-2 border-gray-200 dark:border-[#3D3D3D]">
                        <div>
                          <label className="block text-sm font-medium mb-2 text-black dark:text-white">
                            Default LLM Model
                          </label>
                          <Input
                            type="text"
                            className="dark:border-[#3D3D3D] dark:bg-background"
                            placeholder={getModelPlaceholder(singleProvider, 'llm')}
                            value={singleDefaultModel}
                            onChange={(e) => {
                              setSingleDefaultModel(e.target.value);
                              clearTestResults();
                            }}
                          />
                          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                            Used by ECC for entity extraction and community summarization during document ingestion
                          </p>
                        </div>

                        <div className="flex items-center space-x-3 mt-3">
                          <input
                            type="checkbox"
                            id="singleUseDifferentChatbot"
                            checked={singleUseDifferentChatbotModel}
                            onChange={(e) => {
                              setSingleUseDifferentChatbotModel(e.target.checked);
                              clearTestResults();
                            }}
                            className="h-4 w-4 rounded border-gray-300 dark:border-[#3D3D3D]"
                          />
                          <label htmlFor="singleUseDifferentChatbot" className="text-sm font-medium text-black dark:text-white">
                            Use different model for Chatbot
                          </label>
                        </div>

                        {singleUseDifferentChatbotModel && (
                          <div>
                            <label className="block text-sm font-medium mb-2 text-black dark:text-white">
                              Chatbot LLM Model
                            </label>
                            <Input
                              type="text"
                              className="dark:border-[#3D3D3D] dark:bg-background"
                              placeholder={getModelPlaceholder(singleProvider, 'llm')}
                              value={singleChatbotModel}
                              onChange={(e) => {
                                setSingleChatbotModel(e.target.value);
                                clearTestResults();
                              }}
                            />
                            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                              Used by chatbot for answering user questions
                            </p>
                          </div>
                        )}
                      </div>
                    </div>

                    <div>
                      <label className="block text-sm font-medium mb-2 text-black dark:text-white">
                        Embedding Model
                      </label>
                      <Input
                        type="text"
                        className="dark:border-[#3D3D3D] dark:bg-background"
                        placeholder={getModelPlaceholder(singleProvider, 'embedding')}
                        value={singleEmbeddingModel}
                        onChange={(e) => {
                          setSingleEmbeddingModel(e.target.value);
                          clearTestResults();
                        }}
                      />
                      <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                        Used for generating vector embeddings of document chunks
                      </p>
                    </div>

                    <div>
                      <label className="block text-sm font-medium mb-2 text-black dark:text-white">
                        Multimodal Model
                      </label>
                      <Input
                        type="text"
                        className="dark:border-[#3D3D3D] dark:bg-background"
                        placeholder={getModelPlaceholder(singleProvider, 'multimodal')}
                        value={multimodalModel}
                        onChange={(e) => {
                          setMultimodalModel(e.target.value);
                          clearTestResults();
                        }}
                      />
                      <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                        Used for processing images and multimodal content
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Multiple Provider Configuration */}
          {useMultipleProviders && (
            <>
              {/* Completion Provider */}
              <div className="bg-white dark:bg-shadeA border border-gray-300 dark:border-[#3D3D3D] rounded-lg p-6">
                <h2 className="text-lg font-semibold mb-4 text-black dark:text-white">
                  Completion Service
                </h2>
                <p className="text-sm text-gray-600 dark:text-[#D9D9D9] mb-6">
                  Configure the LLM models used by the ECC service for document processing (entity extraction and community summarization) and by the chatbot for user query responses
                </p>

                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium mb-2 text-black dark:text-white">
                      Provider
                    </label>
                    <Select value={completionProvider} onValueChange={(value) => handleProviderChange(value, 'completion')}>
                      <SelectTrigger className="dark:border-[#3D3D3D] dark:bg-background">
                        <SelectValue placeholder="Select provider" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="openai">OpenAI</SelectItem>
                        <SelectItem value="azure">Azure OpenAI</SelectItem>
                        <SelectItem value="genai">Google GenAI (Gemini)</SelectItem>
                        <SelectItem value="vertexai">Google Vertex AI</SelectItem>
                        <SelectItem value="bedrock">AWS Bedrock</SelectItem>
                        <SelectItem value="sagemaker">AWS SageMaker</SelectItem>
                        <SelectItem value="groq">Groq</SelectItem>
                        <SelectItem value="ollama">Ollama</SelectItem>
                        <SelectItem value="huggingface">HuggingFace</SelectItem>
                        <SelectItem value="watsonx">IBM WatsonX</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  {renderProviderFields(completionProvider, completionConfig, setCompletionConfig)}

                  <div>
                    <label className="block text-sm font-medium mb-2 text-black dark:text-white">
                      Completion Models
                    </label>
                    
                    <div className="space-y-3 pl-4 border-l-2 border-gray-200 dark:border-[#3D3D3D]">
                      <div>
                        <label className="block text-sm font-medium mb-2 text-black dark:text-white">
                          Default LLM Model
                        </label>
                        <Input
                          type="text"
                          className="dark:border-[#3D3D3D] dark:bg-background"
                          placeholder={getModelPlaceholder(completionProvider, 'llm')}
                          value={completionDefaultModel}
                          onChange={(e) => {
                            setCompletionDefaultModel(e.target.value);
                            clearTestResults();
                          }}
                        />
                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                          Used by ECC for entity extraction and community summarization during document ingestion
                        </p>
                      </div>

                      <div className="flex items-center space-x-3 mt-3">
                        <input
                          type="checkbox"
                          id="completionUseDifferentChatbot"
                          checked={completionUseDifferentChatbotModel}
                          onChange={(e) => {
                            setCompletionUseDifferentChatbotModel(e.target.checked);
                            clearTestResults();
                          }}
                          className="h-4 w-4 rounded border-gray-300 dark:border-[#3D3D3D]"
                        />
                        <label htmlFor="completionUseDifferentChatbot" className="text-sm font-medium text-black dark:text-white">
                          Use different model for Chatbot
                        </label>
                      </div>

                      {completionUseDifferentChatbotModel && (
                        <div>
                          <label className="block text-sm font-medium mb-2 text-black dark:text-white">
                            Chatbot LLM Model
                          </label>
                          <Input
                            type="text"
                            className="dark:border-[#3D3D3D] dark:bg-background"
                            placeholder={getModelPlaceholder(completionProvider, 'llm')}
                            value={completionChatbotModel}
                            onChange={(e) => {
                              setCompletionChatbotModel(e.target.value);
                              clearTestResults();
                            }}
                          />
                          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                            Used by chatbot for answering user questions
                          </p>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>

              {/* Embedding Service Provider */}
              <div className="bg-white dark:bg-shadeA border border-gray-300 dark:border-[#3D3D3D] rounded-lg p-6">
                <h2 className="text-lg font-semibold mb-4 text-black dark:text-white">
                  Embedding Service
                </h2>
                <p className="text-sm text-gray-600 dark:text-[#D9D9D9] mb-6">
                  Configure the provider for generating embeddings.
                </p>

                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium mb-2 text-black dark:text-white">
                      Provider
                    </label>
                    <Select value={embeddingProvider} onValueChange={(value) => handleProviderChange(value, 'embedding')}>
                      <SelectTrigger className="dark:border-[#3D3D3D] dark:bg-background">
                        <SelectValue placeholder="Select provider" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="openai">OpenAI</SelectItem>
                        <SelectItem value="azure">Azure OpenAI</SelectItem>
                        <SelectItem value="genai">Google GenAI</SelectItem>
                        <SelectItem value="vertexai">Google Vertex AI</SelectItem>
                        <SelectItem value="bedrock">AWS Bedrock</SelectItem>
                        <SelectItem value="ollama">Ollama</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  {renderProviderFields(embeddingProvider, embeddingConfig, setEmbeddingConfig)}

                  <div>
                    <label className="block text-sm font-medium mb-2 text-black dark:text-white">
                      Embedding Model
                    </label>
                    <Input
                      type="text"
                      className="dark:border-[#3D3D3D] dark:bg-background"
                      placeholder={getModelPlaceholder(embeddingProvider, 'embedding')}
                      value={embeddingModel}
                      onChange={(e) => {
                        setEmbeddingModel(e.target.value);
                        clearTestResults();
                      }}
                    />
                  </div>
                </div>
              </div>

              {/* Multimodal Service Provider */}
              <div className="bg-white dark:bg-shadeA border border-gray-300 dark:border-[#3D3D3D] rounded-lg p-6">
                <h2 className="text-lg font-semibold mb-4 text-black dark:text-white">
                  Multimodal Service
                </h2>
                <p className="text-sm text-gray-600 dark:text-[#D9D9D9] mb-6">
                  Configure the provider for processing images and multimodal content (vision tasks).
                </p>

                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium mb-2 text-black dark:text-white">
                      Provider
                    </label>
                    <Select value={multimodalProvider} onValueChange={(value) => handleProviderChange(value, 'multimodal')}>
                      <SelectTrigger className="dark:border-[#3D3D3D] dark:bg-background">
                        <SelectValue placeholder="Select provider" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="openai">OpenAI</SelectItem>
                        <SelectItem value="azure">Azure OpenAI</SelectItem>
                        <SelectItem value="genai">Google GenAI (Gemini)</SelectItem>
                        <SelectItem value="vertexai">Google Vertex AI</SelectItem>
                      </SelectContent>
                    </Select>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                      Only OpenAI, Azure, GenAI, VertexAI support vision
                    </p>
                  </div>

                  {renderProviderFields(multimodalProvider, multimodalConfig, setMultimodalConfig)}

                  <div>
                    <label className="block text-sm font-medium mb-2 text-black dark:text-white">
                      Model Name
                    </label>
                    <Input
                      type="text"
                      className="dark:border-[#3D3D3D] dark:bg-background"
                      placeholder={getModelPlaceholder(multimodalProvider, 'multimodal')}
                      value={multimodalModelName}
                      onChange={(e) => {
                        setMultimodalModelName(e.target.value);
                        clearTestResults();
                      }}
                    />
                  </div>
                </div>
              </div>
            </>
          )}

          {message && (
            <div
              className={`p-4 rounded-lg text-sm mb-4 ${
                messageType === "success"
                  ? "bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-300"
                  : "bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300"
              }`}
            >
              {message}
            </div>
          )}

          {/* Test Results */}
          {testResults && (
            <div className="space-y-3 mb-4">
              <h3 className="text-sm font-semibold text-black dark:text-white">Connection Test Results:</h3>
              
              {testResults.completion && testResults.completion.status !== "not_tested" && (
                <div className={`p-3 rounded-lg text-sm ${
                  testResults.completion.status === "success"
                    ? "bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-300"
                    : "bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300"
                }`}>
                  <strong>Default LLM Model:</strong> {testResults.completion.message}
                </div>
              )}
              
              {testResults.chatbot && testResults.chatbot.status !== "not_tested" && (
                <div className={`p-3 rounded-lg text-sm ${
                  testResults.chatbot.status === "success"
                    ? "bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-300"
                    : "bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300"
                }`}>
                  <strong>Chatbot LLM Model:</strong> {testResults.chatbot.message}
                </div>
              )}
              
              {testResults.embedding && testResults.embedding.status !== "not_tested" && (
                <div className={`p-3 rounded-lg text-sm ${
                  testResults.embedding.status === "success"
                    ? "bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-300"
                    : "bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300"
                }`}>
                  <strong>Embedding Model:</strong> {testResults.embedding.message}
                </div>
              )}
              
              {testResults.multimodal && testResults.multimodal.status !== "not_tested" && (
                <div className={`p-3 rounded-lg text-sm ${
                  testResults.multimodal.status === "success"
                    ? "bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-300"
                    : "bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300"
                }`}>
                  <strong>Multimodal Model:</strong> {testResults.multimodal.message}
                </div>
              )}
            </div>
          )}

          {/* Buttons */}
          <div className="flex gap-3">
            {!isChatbotOnlyMode && (
              <Button
                onClick={handleTestConnection}
                disabled={isTesting || isSaving}
                className="flex-1 bg-blue-600 hover:bg-blue-700 text-white"
              >
                <CheckCircle2 className="h-4 w-4 mr-2" />
                {isTesting ? "Testing..." : "Test Connection"}
              </Button>
            )}

            <Button 
              onClick={handleSave} 
              disabled={isSaving || isTesting || (!isChatbotOnlyMode && !connectionTested)}
              className="gradient text-white flex-1"
            >
              {isSaving ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  <Save className="h-4 w-4 mr-2" />
                  Save Configuration
                </>
              )}
            </Button>
          </div>
        </div>
        </fieldset>
      </div>
    </div>
  );
};

export default LLMConfig;
