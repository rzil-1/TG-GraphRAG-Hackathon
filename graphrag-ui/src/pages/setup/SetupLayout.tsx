import React from "react";
import { Outlet, useNavigate, useLocation } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { ArrowLeft, Database, Settings, FileText, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

const SetupLayout = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [userRoles, setUserRoles] = React.useState<string[]>([]);
  const [graphRoles, setGraphRoles] = React.useState<Record<string, string[]>>({});
  const [rolesLoaded, setRolesLoaded] = React.useState(false);
  const [hasCreds, setHasCreds] = React.useState(false);
  const isSuperuser = userRoles.includes("superuser");
  const isGlobalDesigner = userRoles.includes("globaldesigner");
  const selectedGraph = localStorage.getItem("selectedGraph") || "";
  const selectedGraphRoles = graphRoles[selectedGraph] || [];
  const isGraphAdmin = selectedGraphRoles.includes("admin");
  const canAccessPrompts = isSuperuser || isGlobalDesigner || isGraphAdmin;
  const canAccessSetup = isSuperuser || isGlobalDesigner || isGraphAdmin;
  const canAccessLlmConfig = isSuperuser || isGlobalDesigner || isGraphAdmin;

  const menuItems = [
    {
      title: "Knowledge Graph Administration",
      icon: Database,
      path: "/setup/kg-admin",
      subItems: [],
    },
    {
      title: "Server Configuration",
      icon: Settings,
      path: "/setup/server-config",
      subItems: [
        ...(canAccessLlmConfig ? [{ title: "LLM Config", path: "/setup/server-config/llm" }] : []),
        ...(isSuperuser ? [{ title: "GraphDB Config", path: "/setup/server-config/graphdb" }] : []),
        ...(isSuperuser || isGlobalDesigner ? [{ title: "GraphRAG Config", path: "/setup/server-config/graphrag" }] : []),
      ],
    },
    {
      title: "Customize Prompts",
      icon: FileText,
      path: "/setup/prompts",
      subItems: [],
    },
  ];

  const visibleMenuItems = menuItems.filter((item) => {
    if (!isSuperuser && !isGlobalDesigner) {
      if (item.path === "/setup/prompts") return canAccessPrompts;
      if (item.path === "/setup/server-config") return canAccessLlmConfig;
      return false;
    }
    return item.path !== "/setup/prompts" || canAccessPrompts;
  });

  const [expandedSection, setExpandedSection] = React.useState<string>("");

  React.useEffect(() => {
    const loadRoles = async () => {
      try {
        const creds = localStorage.getItem("creds");
        if (!creds) {
          setUserRoles([]);
          setGraphRoles({});
          setHasCreds(false);
          setRolesLoaded(true);
          return;
        }
        const response = await fetch("/ui/roles", {
          headers: { Authorization: `Basic ${creds}` },
        });
        if (!response.ok) {
          setUserRoles([]);
          setGraphRoles({});
          setHasCreds(false);
          setRolesLoaded(true);
          return;
        }
        const data = await response.json();
        const roles = Array.isArray(data.roles) ? data.roles : [];
        setUserRoles(roles.map((role: string) => role.toLowerCase()));
        setGraphRoles(
          data.graph_roles && typeof data.graph_roles === "object"
            ? Object.fromEntries(
                Object.entries(data.graph_roles).map(([graph, roles]) => [
                  graph,
                  Array.isArray(roles)
                    ? roles.map((role: string) => role.toLowerCase())
                    : [],
                ])
              )
            : {}
        );
        setHasCreds(true);
      } finally {
        setRolesLoaded(true);
      }
    };
    loadRoles();

    // Auto-expand section based on current path
    const currentSection = menuItems.find(
      (item) => location.pathname.startsWith(item.path)
    );
    if (currentSection) {
      setExpandedSection(currentSection.path);
    }
  }, [location.pathname]);

  React.useEffect(() => {
    if (rolesLoaded && (!hasCreds || !canAccessSetup)) {
      navigate("/", { replace: true });
    }
    if (
      rolesLoaded &&
      isGraphAdmin &&
      !isSuperuser &&
      !isGlobalDesigner &&
      !location.pathname.startsWith("/setup/prompts") &&
      !location.pathname.startsWith("/setup/server-config/llm")
    ) {
      navigate("/setup/server-config/llm", { replace: true });
    }
    if (
      rolesLoaded &&
      !isSuperuser &&
      location.pathname.startsWith("/setup/server-config/graphdb")
    ) {
      navigate("/setup/server-config/llm", { replace: true });
    }
    if (
      rolesLoaded &&
      !isSuperuser &&
      !isGlobalDesigner &&
      location.pathname.startsWith("/setup/server-config/graphrag")
    ) {
      navigate("/setup/server-config/llm", { replace: true });
    }
  }, [
    rolesLoaded,
    hasCreds,
    canAccessSetup,
    isGraphAdmin,
    isSuperuser,
    isGlobalDesigner,
    canAccessLlmConfig,
    location.pathname,
    navigate,
  ]);

  const isActive = (path: string) => {
    return location.pathname === path;
  };

  const isParentActive = (path: string) => {
    return location.pathname.startsWith(path);
  };

  if (rolesLoaded && (!hasCreds || !canAccessSetup)) {
    return null;
  }

  return (
    <div className="flex h-screen bg-white dark:bg-background">
      {/* Sidebar */}
      <div className="w-72 border-r border-gray-300 dark:border-[#3D3D3D] flex flex-col">
        <div className="p-6 border-b border-gray-300 dark:border-[#3D3D3D]">
          <Button
            variant="outline"
            onClick={() => navigate("/chat")}
            className="mb-4 w-full dark:border-[#3D3D3D]"
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Chat
          </Button>
          <h1 className="text-xl font-bold text-black dark:text-white">
            Setup & Configuration
          </h1>
          <p className="text-xs text-gray-600 dark:text-[#D9D9D9] mt-1">
            Manage your system settings
          </p>
        </div>

        {/* Navigation Menu */}
        <nav className="flex-1 overflow-y-auto p-4">
          <div className="space-y-2">
            {visibleMenuItems.map((item) => {
              const Icon = item.icon;
              const hasSubItems = item.subItems.length > 0;
              const isExpanded = expandedSection === item.path;
              const isItemActive = isParentActive(item.path);

              return (
                <div key={item.path}>
                  <button
                    onClick={() => {
                      if (hasSubItems) {
                        setExpandedSection(isExpanded ? "" : item.path);
                      } else {
                        navigate(item.path);
                      }
                    }}
                    className={cn(
                      "w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
                      isItemActive
                        ? "bg-tigerOrange/10 text-tigerOrange"
                        : "text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-[#2A2A2A]"
                    )}
                  >
                    <div className="flex items-center gap-3">
                      <Icon className="h-4 w-4" />
                      <span>{item.title}</span>
                    </div>
                    {hasSubItems && (
                      <ChevronRight
                        className={cn(
                          "h-4 w-4 transition-transform",
                          isExpanded && "rotate-90"
                        )}
                      />
                    )}
                  </button>

                  {/* Sub-items */}
                  {hasSubItems && isExpanded && (
                    <div className="ml-7 mt-1 space-y-1">
                      {item.subItems.map((subItem) => (
                        <button
                          key={subItem.path}
                          onClick={() => navigate(subItem.path)}
                          className={cn(
                            "w-full text-left px-3 py-2 rounded-lg text-sm transition-colors",
                            isActive(subItem.path)
                              ? "bg-tigerOrange/10 text-tigerOrange font-medium"
                              : "text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-[#2A2A2A]"
                          )}
                        >
                          {subItem.title}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </nav>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto">
        <Outlet />
      </div>
    </div>
  );
};

export default SetupLayout;

